from pydantic import BaseModel


class AudioRequest(BaseModel):
    audio_file: str
