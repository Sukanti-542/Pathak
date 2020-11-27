import shutil
import six
from google.cloud import texttospeech
from google.cloud import translate_v2 as translate
from flask import Flask, jsonify, send_file
from flask_restful import Api, Resource, reqparse
import os
from google.cloud.texttospeech_v1beta1 import SsmlVoiceGender
import werkzeug
from werkzeug.utils import secure_filename
# We use secure_filename from the module werkzeug.utils.
# This is essential as we need to sanitize the file name before using it anywhere

# Update path of google key
os.environ['GOOGLE_APPLICATION_CREDENTIALS'] = "PATH TO KEY.json"
# Path where the generated audio is stored
storagePath = './storage/'
# Path where the translated audio is stored
translatePath = './translate/'
# Initiate the TexttoSpeech Client
client = texttospeech.TextToSpeechClient()


# Function to generate the translated text and audio from translated text


def translate_text(text, selected_language_code, selected_gender, selected_voice):
    translate_client = translate.Client()
    if isinstance(text, six.binary_type):
        text = text.decode("utf-8")
    # Text can also be a sequence of strings, in which case this method
    # will return a sequence of results for each text.
    result = translate_client.translate(text, target_language='hi')
    generated_audio = generate_audio(result['translatedtext'], selected_language_code, selected_voice)
    with open(os.path.join(translatePath, 'audio.mp3'),
              "wb") as out:
        # Write the response to the output file.
        out.write(generated_audio)
    return translatePath + 'audio.mp3'


# Function to generate the audio from text
def generate_audio(text, language, voice_type):
    synthesis_input = texttospeech.SynthesisInput(text=text)

    # Build the voice request, select the language code ("en-US") and the ssml
    voice = texttospeech.VoiceSelectionParams(
        language_code=language, name=voice_type
    )

    # Select the type of audio file you want returned. We have selected mp3 format here
    audio_config = texttospeech.AudioConfig(
        audio_encoding=texttospeech.AudioEncoding.MP3
    )
    #
    # Perform the text-to-speech request on the text input with the selected
    # voice parameters and audio file type
    response = client.synthesize_speech(
        input=synthesis_input, voice=voice, audio_config=audio_config
    )
    #
    # The response's audio_content is binary.
    # with open("output.mp3", "wb") as out:
    # Write the response to the output file.
    return response.audio_content
    # print('Audio content written to file "output.mp3"')


# Function to fetch all languages supported for generating audio from text and generate a dictionary. This allows
# for more flexibility and better user experience when the dictionary is sent via an api and is
# displayed using dropdowns in the UI. This logic is currently only for Indian Languages and can be modified as
# required


def get_languages():
    list_languages = ['bn-IN', 'gu-IN', 'hi-IN', 'kn-IN', 'ta-IN', 'te-IN']
    list_of_voices = {}
    voices = client.list_voices().voices  # Fetch the list of voices from google
    print(voices)
    final_list_of_voices = []
    for voice in voices:
        for language_codes in voice.language_codes:
            if list_languages.count(language_codes) > 0:
                list_of_voices.setdefault(language_codes, []).append(
                    {'voice': voice.name, 'gender': SsmlVoiceGender(voice.ssml_gender).name})
                # Generate a dictionary of list of voices

    for key in list_of_voices:
        if key == 'bn-IN':
            language = 'Bengali'
        elif key == 'gu-IN':
            language = 'Gujarati'
        elif key == 'hi-IN':
            language = 'Hindi'
        elif key == 'kn-IN':
            language = 'Kannada'
        elif key == 'ta-IN':
            language = 'Tamil'
        elif key == 'te-IN':
            language = 'Telugu'
        final_list_of_voices.append({'language': language, 'language_code': key, 'voices': list_of_voices[key]})
        # generate a dictionary which has the readable language name, the language code, and the list of voices
    return final_list_of_voices


app = Flask(__name__)
api = Api(app)


class Languages(Resource):
    def get(self):
        return jsonify(get_languages())
        # Return the dictionary generated in a json format


class GenerateAudio(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        # Define the request parameters
        parser.add_argument('upload_file', location='files', type=werkzeug.datastructures.FileStorage,
                            help='Send File To Upload')
        parser.add_argument('language', type=str, help='No Language Selected')
        parser.add_argument('language_code', type=str, help='No Language Selected')
        parser.add_argument('gender', type=str, help='No Language Selected')
        parser.add_argument('voice', type=str, help='No Language Selected')
        # Fetch the request parameters
        args = parser.parse_args()
        file = args['upload_file']
        selected_language = args['language']
        selected_language_code = args['language_code']
        selected_gender = args['gender']
        selected_voice = args['voice']
        # Generate the path of the directory where the generated audio should be stored. For each file
        # the script creates a new directory with the name of the file and stores te sent file along with the
        # generated audio in the same directory
        path = os.path.join(storagePath, secure_filename(
            file.filename) + '----' + selected_language + '----' + selected_gender + '----' + selected_voice)

        file_content = file.read()
        # Check is the directory already exists. os.mkdir returns an error if the path is already present
        if os.path.exists(path):
            # Remove the directory if it already exists
            shutil.rmtree(path)
        # Create the directory
        os.mkdir(path)
        # Write the file sent to the directory.
        with open(os.path.join(path, secure_filename(file.filename).split('.')[0]
                                     + '----' + selected_language + '----' + selected_gender
                                     + '----' + selected_voice + '.' + secure_filename(file.filename).split('.')[1]),
                  "wb") as file1:
            file1.write(file_content)

        generated_audio = generate_audio(file_content, selected_language_code, selected_voice)
        # Write the generated audio as an mp3 file to the directory
        with open(os.path.join(path, secure_filename(file.filename).split('.')[0]
                                     + '----' + selected_language + '----' + selected_gender
                                     + '----' + selected_voice + '.mp3'),
                  "wb") as out:
            # Write the response to the output file.
            out.write(generated_audio)
            # Return the saved audio file as response to the API
            return send_file(os.path.join(path, secure_filename(file.filename).split('.')[
                0] + '----' + selected_language + '----' + selected_gender + '----' + selected_voice + '.mp3'),
                             mimetype="audio/wav", as_attachment=True, attachment_filename=file.filename + '.mp3')


class GenerateTranslatedAudio(Resource):
    def post(self):
        parser = reqparse.RequestParser()
        # Define the request parameters
        parser.add_argument('upload_file', type=str,
                            help='Send File To Upload')
        parser.add_argument('language', type=str, help='No Language Selected')
        parser.add_argument('language_code', type=str, help='No Language Selected')
        parser.add_argument('gender', type=str, help='No Language Selected')
        parser.add_argument('voice', type=str, help='No Language Selected')
        # Fetch the request parameters
        args = parser.parse_args()
        file = args['upload_file']
        selected_language_code = args['language_code']
        selected_gender = args['gender']
        selected_voice = args['voice']
        return send_file(translate_text(file, selected_language_code, selected_gender, selected_voice),
                         mimetype="audio/wav", as_attachment=True)


# Add resource class for each api
api.add_resource(Languages, '/get-languages/', endpoint='getlanguages')
api.add_resource(GenerateAudio, '/upload-file/', endpoint='uploadfile')
api.add_resource(GenerateTranslatedAudio, '/translate-speech/', endpoint='translatespeech')
