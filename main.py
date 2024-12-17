from fastapi import FastAPI, UploadFile, File, HTTPException
import os
import subprocess
import vosk
import wave
import json

import subprocess


app = FastAPI()

# Загрузка модели VOSK
model = vosk.Model('vosk-model-small-ru-0.22')

def convert_mp3_to_wav(mp3_path):
    wav_path = mp3_path.replace('.mp3', '.wav')
    command = ['ffmpeg', '-i', mp3_path, '-ac', '1', '-ar', '16000', wav_path]
    try:
        subprocess.run(command, check=True)
        return wav_path
    except FileNotFoundError:
        raise Exception("FFmpeg не найден. Убедитесь, что он установлен и добавлен в PATH.")
    except subprocess.CalledProcessError as e:
        print(f"Ошибка при конвертации: {e.stderr.decode()}")
        return None



@app.post('/asr')
async def asr(file: UploadFile = File(...)):
    # Сохраняем загруженный файл во временную директорию
    file_location = f"temp/{file.filename}"
    
    with open(file_location, "wb") as f:
        f.write(await file.read())

    # Проверяем формат файла
    if not file.filename.endswith('.mp3'):
        raise HTTPException(status_code=400, detail='Файл должен быть в формате MP3.')

    # Конвертируем MP3 в WAV
    wav_file_path = convert_mp3_to_wav(file_location)

    # Проверяем, был ли создан WAV файл
    if wav_file_path is None or not os.path.exists(wav_file_path):
        raise HTTPException(status_code=500, detail='Не удалось создать WAV файл.')

    # Обработка аудиофайла с использованием VOSK
    with wave.open(wav_file_path, "rb") as wf:
        if wf.getnchannels() != 1 or wf.getframerate() != 16000:
            raise HTTPException(status_code=400,
                                detail='Аудиофайл должен быть моно и иметь частоту дискретизации 16000 Гц.')
        
        rec = vosk.KaldiRecognizer(model, wf.getframerate())
        
        dialog = []
        result_duration = {"receiver": 0, "transmitter": 0}
        
        last_source = None
        
        while True:
            data = wf.readframes(4000)
            if len(data) == 0:
                break
            
            if rec.AcceptWaveform(data):
                result = json.loads(rec.Result())
                text = result.get('text', '')
                
                if text:
                    # Определяем источник на основе предыдущего значения
                    if last_source == 'receiver':
                        source = 'transmitter'
                    else:
                        source = 'receiver'

                    duration = len(text.split())
                    gender = 'male' if source == 'receiver' else 'female'
                    raised_voice = True if '!' in text else False

                    dialog.append({
                        "source": source,
                        "text": text,
                        "duration": duration,
                        "raised_voice": raised_voice,
                        "gender": gender
                    })

                    result_duration[source] += duration  
                    last_source = source

    # Удаляем временные файлы
    os.remove(file_location)
    os.remove(wav_file_path)

    return {
        "dialog": dialog,
        "result_duration": result_duration
    }
