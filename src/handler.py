#!/usr/bin/env python
import os

from bark import preload_models, generate_audio, SAMPLE_RATE
from scipy.io.wavfile import write as write_wav

import runpod
from runpod.serverless.utils import rp_download, rp_cleanup, rp_upload
from runpod.serverless.utils.rp_validator import validate

from supabase import create_client

from schemas import INPUT_SCHEMA

# Load the Bark models
preload_models()

def generate_bark_audio(job):
    job_input = job["input"]
    
    # Input validation
    validated_input = validate(job_input, INPUT_SCHEMA)
    
    if 'errors' in validated_input:
        return {"error": validated_input['errors']}
    validated_input = validated_input['validated_input']
    
    # Generate audio from text
    text_prompt = validated_input['text_prompt']
    voice_preset = validated_input.get('voice_preset', None)

    try:
        audio_array = generate_audio(text_prompt, history_prompt=voice_preset)
    except Exception as e:
        return {"error": f"Failed to generate audio: {str(e)}"}
    
    # Save to temporary file
    temp_file = f"/tmp/{job['id']}.wav"
    write_wav(temp_file, SAMPLE_RATE, audio_array)
    
    try:
        # Initialize Supabase client
        supabase = create_client(
            os.environ["SUPABASE_URL"],
            os.environ["SUPABASE_KEY"]
        )
        bucket_name = os.environ["SUPABASE_BUCKET_NAME"]
        
        # Upload to Supabase Storage
        with open(temp_file, 'rb') as f:
            response = supabase.storage.from_(bucket_name).upload(
                file=f,
                path=f"{job['id']}.wav",
                file_options={"content-type": "audio/wav"}
            )
            
        # Get public URL
        public_url = supabase.storage.from_(bucket_name).get_public_url(f"{job['id']}.wav")
        
        return {
            "audio_url": public_url
        }
    except Exception as e:
        return {"error": f"Failed to upload audio: {str(e)}"}
    finally:
        # Cleanup temporary file
        if os.path.exists(temp_file):
            os.remove(temp_file)

runpod.serverless.start({"handler": generate_bark_audio})
