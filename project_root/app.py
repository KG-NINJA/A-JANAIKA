from flask import Flask, render_template, request, jsonify, send_from_directory
import os
import google.generativeai as genai
import json
from midiutil import MIDIFile # Added import

app = Flask(__name__)
MIDI_DIR = os.path.join(app.root_path, 'generated_midi')
os.makedirs(MIDI_DIR, exist_ok=True)
app.config['MIDI_DIR'] = MIDI_DIR

try:
    GOOGLE_API_KEY = os.environ.get("GEMINI_API_KEY")
    if not GOOGLE_API_KEY:
        print("WARNING: GEMINI_API_KEY environment variable not set.")
    genai.configure(api_key=GOOGLE_API_KEY)
except Exception as e:
    print(f"Error configuring Gemini API: {e}")

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/compose', methods=['POST'])
def compose_melody():
    data = request.get_json()
    melody_data = data.get('melody')

    if not melody_data:
        return jsonify({"error": "No melody data received"}), 400

    print(f"Received placeholder melody data: {melody_data}")

    # Extract tempo from melody_data, default to 120 if not provided
    tempo = melody_data.get('tempo', 120)

    prompt_parts = [
        "You are an expert music composer.",
        "Given the following input melody as a JSON object with 'notes' (each note having 'pitch' as MIDI number, 'startTime' in seconds, 'endTime' in seconds) and 'tempo' in BPM:",
        json.dumps(melody_data),
        "Compose a suitable accompaniment for this melody.",
        "Return the accompaniment as a JSON object with a key 'accompaniment_notes'.",
        "'accompaniment_notes' should be a list of notes, where each note is an object with:",
        "  - 'pitch': MIDI number (integer, e.g., 60 for C4).",
        "  - 'startTime': The time (in seconds, float, relative to the start of the composition) when the note should start.",
        "  - 'duration': The duration (in seconds, float) for which the note should play.",
        "  - 'volume': MIDI velocity (integer, 0-127, e.g., 100).",
        "  - 'instrument' (optional): A string like 'piano', 'bass', 'drums'. If provided, I will try to map it to a MIDI program. For now, I will primarily use the pitch, startTime, duration, and volume.",
        "The accompaniment should be harmonically and rhythmically interesting and complement the original melody.",
        "Ensure the startTime of accompaniment notes aligns with the original melody's timing and overall tempo.",
        "Example of a single accompaniment note: {'pitch': 55, 'startTime': 0.0, 'duration': 0.5, 'volume': 90, 'instrument': 'piano'}"
    ]
    prompt = "\n".join(prompt_parts)

    print("\n--- Sending Prompt to Gemini ---")
    # print(prompt) # Keep it commented for brevity unless debugging
    print("Prompt sent (content omitted for brevity)")
    print("------------------------------\n")

    try:
        if not GOOGLE_API_KEY:
             return jsonify({"error": "Gemini API key not configured on the server."}), 500

        model = genai.GenerativeModel('gemini-pro')
        response = model.generate_content(prompt)

        print("\n--- Received Response from Gemini ---")
        if response.parts:
            response_text = response.text
            # print(f"Raw response text: {response_text}") # Keep commented for brevity

            if response_text.strip().startswith("```json"):
                response_text = response_text.strip()[7:-3].strip()
            elif response_text.strip().startswith("```"):
                 response_text = response_text.strip()[3:-3].strip()

            try:
                gemini_output = json.loads(response_text)
                accompaniment_notes = gemini_output.get("accompaniment_notes")
            except json.JSONDecodeError as e:
                print(f"Error decoding Gemini JSON response: {e}")
                print(f"Problematic response text: {response_text}") # Log the problematic text
                return jsonify({"error": "Could not parse music data from Gemini.", "details": str(e), "response_text": response_text}), 500

            if not accompaniment_notes or not isinstance(accompaniment_notes, list):
                print("Gemini response did not contain a valid list of 'accompaniment_notes'.")
                return jsonify({"error": "Gemini did not return valid accompaniment notes.", "gemini_response": response.text}), 500

            print(f"Successfully parsed {len(accompaniment_notes)} accompaniment notes.")

            # Convert accompaniment_notes to MIDI
            # For simplicity, we'll put all accompaniment notes on one track (track 0 for melody, track 1 for accompaniment)
            # And use a default MIDI program (e.g., acoustic grand piano)

            output_midi_filename = f"composition_{os.urandom(4).hex()}.mid"
            output_midi_path = os.path.join(app.config['MIDI_DIR'], output_midi_filename)

            # Create MIDIFile object
            # 1 track for the original melody (placeholder), 1 for accompaniment.
            # We could also add the original melody notes from `melody_data` to the MIDI.
            mf = MIDIFile(2, removeDuplicates=True, deinterleave=False) # 2 tracks

            # Add track names and tempo
            # Track 0 for original melody (if we decide to include it)
            # Track 1 for accompaniment
            track_accompaniment = 1
            time_accompaniment = 0 # Start time for adding notes to the track

            mf.addTrackName(track_accompaniment, time_accompaniment, "Accompaniment")
            mf.addTempo(track_accompaniment, time_accompaniment, tempo)

            # Add original melody notes to MIDI (Track 0) - Optional, but good for context
            track_melody = 0
            time_melody = 0
            mf.addTrackName(track_melody, time_melody, "Original Melody")
            mf.addTempo(track_melody, time_melody, tempo)

            input_melody_notes = melody_data.get('notes', [])
            for note_info in input_melody_notes:
                pitch = note_info.get('pitch')
                start_time_sec = note_info.get('startTime')
                end_time_sec = note_info.get('endTime')
                duration_sec = end_time_sec - start_time_sec

                # Convert seconds to beats (MIDIUtil uses beats)
                # duration_beats = (duration_sec / 60.0) * tempo  # Incorrect calculation for beats
                duration_beats = duration_sec * (tempo / 60.0)


                if pitch is not None and start_time_sec is not None and duration_beats > 0:
                    # MIDIUtil addNote: track, channel, pitch, time (beats), duration (beats), volume
                    # Time also needs to be in beats: start_time_beats = (start_time_sec / 60.0) * tempo
                    start_time_beats = start_time_sec * (tempo / 60.0)
                    mf.addNote(track_melody, 0, pitch, start_time_beats, duration_beats, 100) # Channel 0, Volume 100

            # Add accompaniment notes from Gemini to MIDI (Track 1)
            for note_info in accompaniment_notes:
                pitch = note_info.get('pitch')
                start_time_sec = note_info.get('startTime') # in seconds from Gemini
                duration_sec = note_info.get('duration')   # in seconds from Gemini
                volume = note_info.get('volume', 90)       # default volume if not provided

                if pitch is None or start_time_sec is None or duration_sec is None:
                    print(f"Skipping invalid note from Gemini: {note_info}")
                    continue

                # Convert seconds to beats for MIDIUtil
                # Beat = (seconds / 60) * BPM
                # So, if tempo is 120 BPM, 1 second = 2 beats.
                # If tempo is 60 BPM, 1 second = 1 beat.
                start_time_beats = start_time_sec * (tempo / 60.0)
                duration_beats = duration_sec * (tempo / 60.0)

                if duration_beats <= 0:
                    print(f"Skipping note with non-positive duration: {note_info}")
                    continue

                # MIDIUtil addNote: track, channel, pitch, time (beats), duration (beats), volume
                mf.addNote(track_accompaniment, 0, pitch, start_time_beats, duration_beats, volume) # Using channel 0 for accompaniment as well for now

            with open(output_midi_path, 'wb') as outf:
                mf.writeFile(outf)

            print(f"MIDI file generated: {output_midi_filename}")

            midi_file_url = f"/download_midi/{output_midi_filename}"

            return jsonify({
                "message": "Composition complete! MIDI file generated.",
                "midi_file_url": midi_file_url,
                "accompaniment_note_count": len(accompaniment_notes)
            })

        else:
            print("Gemini response was empty or blocked.")
            error_details = "Unknown error"
            if response.prompt_feedback:
                error_details = f"Prompt feedback: {response.prompt_feedback}"
            return jsonify({"error": "Failed to get a valid response from Gemini.", "details": error_details}), 500

    except Exception as e:
        print(f"Error during MIDI generation or Gemini API call: {e}")
        import traceback
        traceback.print_exc() # Print full traceback for debugging
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500

@app.route('/download_midi/<filename>')
def download_midi(filename):
    return send_from_directory(app.config['MIDI_DIR'], filename, as_attachment=True, mimetype='audio/midi')

if __name__ == '__main__':
    if not GOOGLE_API_KEY:
        print("CRITICAL: GEMINI_API_KEY is not set. The application may not function correctly.")
    app.run(debug=True)
