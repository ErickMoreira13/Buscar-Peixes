import unicodedata
from pytube import Search
import os
import yt_dlp as youtube_dl

from moviepy.editor import VideoFileClip
from google.cloud import speech_v1p1beta1 as speech
from pydub import AudioSegment
import csv
import tempfile

# Buscar no YouTube
def search_youtube(query, max_results=5):
    try:
        search = Search(query)
        results = search.results
        videos = []

        for result in results[:max_results]:
            videos.append({
                'title': result.title,
                'url': result.watch_url,
            })

        return videos

    except Exception as e:
        print(f"Erro ao buscar vídeos: {e}")
        
        return []

# Baixando o vídeo
def download_video(url, temp_dir):
    try:
        ydl_opts = {
            'outtmpl': os.path.join(temp_dir, '%(title)s.%(ext)s'),
            'format': 'best'
        }

        with youtube_dl.YoutubeDL(ydl_opts) as ydl:
            info_dict = ydl.extract_info(url, download=True)
            video_path = ydl.prepare_filename(info_dict)
            print(f"Download concluído para: {url}")

            return video_path

    except Exception as e:
        print(f"Erro ao baixar o vídeo: {e}")

        return None

# Extraindo o audio do vídeo
def extract_audio_from_video(video_path, audio_path):
    video = VideoFileClip(video_path)
    video.audio.write_audiofile(audio_path, codec="pcm_s16le")
    video.close()

# Convertendo o audio para mono
def convert_to_mono(audio_path):
    sound = AudioSegment.from_file(audio_path)
    mono_sound = sound.set_channels(1)
    mono_sound.export(audio_path, format="wav")
    
    print(f"Áudio convertido para mono: {audio_path}")

# Dividindo o audio em n partes com basse em um determinado tempo (ms)
def split_audio(audio_path, segment_duration_ms=30000):
    sound = AudioSegment.from_file(audio_path)
    segments = []

    for i in range(0, len(sound), segment_duration_ms):
        segment = sound[i:i + segment_duration_ms]
        segments.append(segment)

    return segments, sound.frame_rate

# Transcrevendo o audio (por partes)
def transcribe_audio_segments(audio_segments, sample_rate):
    client = speech.SpeechClient()
    full_transcription = ""

    for i, segment in enumerate(audio_segments):
        print(f"Transcrevendo partes {i + 1}/{len(audio_segments)}...")
        audio_content = segment.raw_data

        audio = speech.RecognitionAudio(content=audio_content)

        config = speech.RecognitionConfig(
            encoding=speech.RecognitionConfig.AudioEncoding.LINEAR16,
            sample_rate_hertz=sample_rate,
            language_code="pt-BR"
        )

        try:
            response = client.recognize(config=config, audio=audio)

            for result in response.results:
                full_transcription += result.alternatives[0].transcript + " "

        except Exception as e:
            print(f"Erro ao transcrever parte {i + 1}: {e}")

    return full_transcription.strip()


# Normalizando o texto
def normalize_text(text):
    return unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("utf-8").lower()

# Identificando se os itens desejados estão na transcrição 
def analyze_transcription(transcription):
    fish_list = ["pirarucu", "pacu", "piranha", "piau", "piazão"]
    found_fish = []

    normalized_transcription = normalize_text(transcription)
    normalized_fish_list = [normalize_text(fish) for fish in fish_list]

    for fish in normalized_fish_list:
        if fish in normalized_transcription:
            found_fish.append(fish)

    return found_fish


# Salva a transcrição no formato '.txt'
def save_transcription(transcription, output_dir, video_id):
    file_path = os.path.join(output_dir, f"{video_id}.txt")

    with open(file_path, "w", encoding="utf-8") as file:
        file.write(transcription)

    print(f"Transcrição salva em: {file_path}")

    return file_path

# Salva os resultados de itens encontrados na transcrição em um arqv '.csv'
def save_results_to_csv(results, output_file):
    with open(output_file, "w", newline="", encoding="utf-8") as csvfile:
        fieldnames = ["Video", "URL", "Peixes Encontrados", "Arquivo de Transcricao"]
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)

        writer.writeheader()
        for result in results:
            writer.writerow(result)

    print(f"Resultados salvos em: {output_file}")

# main
if __name__ == "__main__":
    # Identificando a "chave" para usar a api do google: 'speach to text' para transcrição
    os.environ["GOOGLE_APPLICATION_CREDENTIALS"] = "credentials.json"

    # Busca e quantidade de vídeos a ser analisados
    query = "Pesca com ceva"
    max_results = 3

    # Nome do diretório da saída de dados (resultados)
    output_dir = "saida_videos"
    os.makedirs(output_dir, exist_ok=True)

    # Usando diretório temporário
    with tempfile.TemporaryDirectory() as temp_dir:
        print(f"Usando diretório temporário: {temp_dir}")

        # Buscando os vídeos
        videos = search_youtube(query, max_results)

        if videos:
            print("\nVídeos encontrados e iniciando download:")
            results = []
            for i, video in enumerate(videos):
                video_id = f"video{i + 1:02d}"
                print(f"{i + 1}. {video['title']} - {video['url']}")
                video_path = download_video(video['url'], temp_dir)

                if video_path:
                    audio_path = os.path.join(temp_dir, "audio.wav")

                    print("Extraindo áudio do vídeo...")
                    extract_audio_from_video(video_path, audio_path)

                    print("Convertendo áudio para mono...")
                    convert_to_mono(audio_path)

                    print("Dividindo áudio em segmentos menores...")
                    segments, sample_rate = split_audio(audio_path)

                    print("Iniciando transcrição de segmentos...")
                    transcription = transcribe_audio_segments(segments, sample_rate)

                    print("\nTranscrição final:\n")
                    print(transcription)

                    transcription_file = save_transcription(transcription, output_dir, video_id)

                    # Identificando os itens encontrados na transcrição
                    found_fish = analyze_transcription(transcription)

                    # Adicionando no arqv '.csv'
                    results.append({
                        "Video": video_id,
                        "URL": video['url'],
                        "Peixes Encontrados": ", ".join(found_fish),
                        "Arquivo de Transcricao": transcription_file
                    })

                    if os.path.exists(audio_path):
                        os.remove(audio_path)
                else:
                    print("Erro no download do vídeo.")

            # Salvando o arqv 'csv'
            output_csv = os.path.join(output_dir, "resultados.csv")
            save_results_to_csv(results, output_csv)

        else:
            print("Nenhum vídeo foi encontrado.")
