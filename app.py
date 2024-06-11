import os
import pymysql
from flask import Flask, render_template, request, redirect, url_for, session, flash, send_from_directory, Response,send_file
from werkzeug.utils import secure_filename
from Bitrate import get_bitrate
from DR import calculate_decibels_with_sampling_rate, plot_waveform_with_sampling_rate
from loudness import get_loudness, plot_loudness
from peak_level import plot_waveform_with_peak
from silence_speech import get_silence_speech_ratio, plot_silence_speech_ratio_pie
from file_utils import calculate_file_size
from harmonicity import get_harmonicity, plot_harmonicity
from frequency import plot_frequency_spectrum
from tempo import estimate_tempo
from datetime import datetime
from io import BytesIO
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from PIL import Image

app = Flask(__name__)
app.secret_key = os.urandom(24)
ALLOWED_EXTENSIONS = {'mp3', 'wav'}
app.config['UPLOAD_FOLDER'] = os.path.join(os.getcwd(), 'uploads')


# Ensure the database and uploads directories exist
if not os.path.exists('database'):
    os.makedirs('database')
if not os.path.exists('uploads'):
    os.makedirs('uploads')

# Initialize the MySQL database
def init_db():
    conn = pymysql.connect(
        host='localhost',
        user='root',       
        password='',  
        db='audio',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    # Check if the tables exist, if not, create them
    cursor.execute('''CREATE TABLE IF NOT EXISTS users (
                        id INT AUTO_INCREMENT PRIMARY KEY,
                        username VARCHAR(255) UNIQUE NOT NULL,
                        email VARCHAR(255) UNIQUE NOT NULL,
                        password VARCHAR(255) NOT NULL)''')
    cursor.execute('''CREATE TABLE IF NOT EXISTS uploads (
                        audio_id INT AUTO_INCREMENT PRIMARY KEY,
                        user_id INT,
                        filename VARCHAR(255) NOT NULL,
                        bitrate INT NOT NULL,
                        loudness_plot_path VARCHAR(255) NOT NULL,
                        waveform_plot_path VARCHAR(255) NOT NULL,
                        silence_speech_ratio_plot_path VARCHAR(255) NOT NULL,
                        frequency_plot_path VARCHAR(255) NOT NULL,
                        plot_path_sr VARCHAR(255) NOT NULL,
                        harmonicity_plot_path VARCHAR(255) NOT NULL,
                        decibels FLOAT,  -- Add decibels column
                        tempo FLOAT,     -- Add tempo column
                        file_size FLOAT, -- Add file_size column
                        FOREIGN KEY (user_id) REFERENCES users(id))''')
    conn.commit()
    conn.close()

# Call init_db() only once when the application starts
init_db()


#Home
@app.route('/')
def index():
    return render_template('index.html')
#signup
@app.route('/signup', methods=['GET', 'POST'])
def signup():
    if request.method == 'POST':
        # Get the username, email, and password from the form
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        
        # Connect to the database
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='audio',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        
        try:
            # Insert new user into the database
            cursor.execute('INSERT INTO users (username, email, password) VALUES (%s, %s, %s)', (username, email, password))
            conn.commit()

            # Set the session value
            session['username'] = username

            conn.close()
            return redirect(url_for('index'))
        except pymysql.MySQLError as e:
            flash("Username already exists")
            conn.close()
    
    return render_template('signup.html')

#login
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        
        # Connect to the MySQL database
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='audio',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        
        try:
            # Fetch user details from the database
            cursor.execute('SELECT * FROM users WHERE username = %s', (username,))
            user = cursor.fetchone()
            
            # Check if user exists and passwords match
            if user and user['password'] == password:  # Check password without hashing
                session['username'] = username
                session['user_id'] = user['id']  # Assuming 'id' is the column name for user ID
                return redirect(url_for('index'))
            else:
                flash("Invalid username or password")
        except pymysql.MySQLError as e:
            flash("Database error")
            print(e)
        finally:
            conn.close()
    
    return render_template('login.html')

#logout
@app.route('/logout')
def logout():
    # Remove the username from the session if it's there
    session.pop('username', None)
    return redirect(url_for('index'))

#upload audio
@app.route('/upload', methods=['GET', 'POST'])
def upload():
    if request.method == 'POST':
        if 'file' not in request.files:
            flash("No file part")
            return redirect(request.url)
        
        file = request.files['file']
        
        if file.filename == '':
            flash("No selected file")
            return redirect(request.url)
        
        if not (file.filename.lower().endswith('.mp3') or file.filename.lower().endswith('.wav')):
            flash("Unsupported file format. Only .mp3 and .wav are allowed.")
            return redirect(request.url)
        
          # Add timestamp to the filename
        timestamp = datetime.now().strftime("%Y%m%d%H%M%S")
        filename = secure_filename(f"{timestamp}_{file.filename}")
        file_path = os.path.join('uploads', filename)
        file.save(file_path)
        
        # Check if the file is saved successfully
        if not os.path.exists(file_path):
            flash("Error saving the file")
            return redirect(request.url)

        # Calculate the bitrate using the get_bitrate function
        bitrate = get_bitrate(file_path)
        
        # Check if bitrate calculation is successful
        if bitrate is None:
            flash("Error calculating bitrate")
            return redirect(request.url)
        username = session.get('username')  # Get username from session

 
        # Plot the waveform with sampling rate and save the plot
        plot_path_sr = plot_waveform_with_sampling_rate(file_path, filename, username)

        # Calculate decibels with sampling rate
        decibels_value = calculate_decibels_with_sampling_rate(file_path, bitrate)
        decibels_with_units = f"{decibels_value:.2f} dB"

        # Plot the loudness and save the plot
        loudness_plot_path = plot_loudness(file_path, filename, username)
        
        # Plot the waveform with peak and save the plot
        waveform_plot_path = plot_waveform_with_peak(file_path, filename, username)

        # Plot the silence speech ratio pie chart and save the plot
        silence_speech_ratio_plot_path = plot_silence_speech_ratio_pie(file_path, filename, username)

        # Plot harmonicity and save the plot
        harmonicity_plot_path = plot_harmonicity(file_path, filename, username)

        # Plot the frequency spectrum and save the plot
        frequency_plot_path = plot_frequency_spectrum(file_path, filename, username)

        # Estimate tempo and save the tempo value
        tempo = estimate_tempo(file_path)

        # Calculate the file size
        file_size_mb = calculate_file_size(file_path)
        
        user_id = session.get('user_id')  # Get user_id from session

        # Connect to MySQL database
        conn = pymysql.connect(
            host='localhost',
            user='root',
            password='',
            db='audio',
            charset='utf8mb4',
            cursorclass=pymysql.cursors.DictCursor
        )
        cursor = conn.cursor()
        
        try:
            # Insert upload details into MySQL database
            cursor.execute('INSERT INTO uploads (user_id,filename, bitrate, plot_path_decibels, waveform_plot_path, silence_speech_ratio_plot_path, frequency_plot_path, plot_path_sr, harmonicity_plot_path,decibals,tempo,file_size) VALUES (%s,%s, %s, %s, %s, %s, %s, %s, %s,%s,%s,%s)', 
                           (user_id,filename, bitrate, loudness_plot_path, waveform_plot_path, silence_speech_ratio_plot_path, frequency_plot_path, plot_path_sr, harmonicity_plot_path,decibels_value,tempo,file_size_mb))
            conn.commit()
            flash(f"File uploaded successfully with bitrate: {bitrate} kbps")
        except pymysql.MySQLError as e:
            flash("Error uploading file to database")
            print(e)
        finally:
            conn.close()
        
        # Pass the paths of the generated graph images and tempo value to the template
        return render_template('upload.html', plot_path_sr_var=plot_path_sr, decibels_var=decibels_with_units, loudness_plot_path=loudness_plot_path, waveform_plot_path=waveform_plot_path, silence_speech_ratio_plot_path=silence_speech_ratio_plot_path, file_size_var=f"{file_size_mb:.2f} MB", bitrate_var=f"{bitrate} kbps", harmonicity_plot_path=harmonicity_plot_path, frequency_plot_path=frequency_plot_path, tempo=tempo)

    return render_template('upload.html')

@app.route('/uploads/<filename>')
def uploaded_file(filename):
    return send_from_directory(app.config['UPLOAD_FOLDER'], filename)

@app.route('/history')
def history():
    user_id = session.get('user_id')  # Get user_id from session
    if user_id is None:
        flash("You need to log in first")
        return redirect(url_for('login'))
    
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='audio',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM uploads WHERE user_id = %s', (user_id,))
    uploads = cursor.fetchall()
    conn.close()

    # Preprocess the paths to replace backslashes with forward slashes
    for upload in uploads:
        if upload.get('plot_path_decibels'):
            upload['loudness_plot_path'] = upload['plot_path_decibels'].replace('\\', '/')
        if upload.get('waveform_plot_path'):
            upload['waveform_plot_path'] = upload['waveform_plot_path'].replace('\\', '/')
        if upload.get('silence_speech_ratio_plot_path'):
            upload['silence_speech_ratio_plot_path'] = upload['silence_speech_ratio_plot_path'].replace('\\', '/')
        if upload.get('frequency_plot_path'):
            upload['frequency_plot_path'] = upload['frequency_plot_path'].replace('\\', '/')
        if upload.get('plot_path_sr'):
            upload['plot_path_sr'] = upload['plot_path_sr'].replace('\\', '/')
        if upload.get('harmonicity_plot_path'):
            upload['harmonicity_plot_path'] = upload['harmonicity_plot_path'].replace('\\', '/')
        
        # Removing timestamp from filename
        filename_parts = upload['filename'].split('_', 1)
        original_filename = filename_parts[1] if len(filename_parts) > 1 else upload['filename']
        upload['original_filename'] = original_filename

    return render_template('history.html', uploads=uploads)


@app.route('/download_record/<int:record_id>')
def download_record(record_id):
    username = session.get('username')
    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='audio',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM uploads WHERE audio_id = %s', (record_id,))
    upload = cursor.fetchone()  # Fetch a single record
    conn.close()
    
    if not upload:
        flash("Record not found")
        return redirect(url_for('history'))

    # Removing timestamp from filename
    filename_parts = upload['filename'].split('_', 1)
    original_filename = filename_parts[1] if len(filename_parts) > 1 else upload['filename']

    # Create a PDF file
    pdf_buffer = BytesIO()
    c = canvas.Canvas(pdf_buffer, pagesize=letter)

    # Add title
    c.setFont("Helvetica-Bold", 16)
    c.drawString(100, 750, "Audio Record Analysis")
    c.setFont("Helvetica", 12)

    # Add metadata
    c.drawString(100, 730, f"Name: {username}")
    c.drawString(100, 710, f"File Name: {original_filename}")
    c.drawString(100, 690, f"Bitrate: {upload['bitrate']} kbps")
    c.drawString(100, 670, f"Decibels: {upload['decibals']}")  # Add decibels
    c.drawString(100, 650, f"Tempo: {upload['tempo']} BPM")    # Add tempo
    c.drawString(100, 630, f"File Size: {upload['file_size']} MB")    # Add size


    # Draw images
    y_position = 610  # Adjust the starting position for drawing images

    def draw_image(image_path, description, c, y_position):
        if y_position < 100:
            c.showPage()  # Start a new page if the current one is full
            c.setFont("Helvetica-Bold", 16)
            c.drawString(100, 750, "Audio Record Analysis (continued)")
            c.setFont("Helvetica", 12)
            y_position = 700
        c.drawString(100, y_position, description)
        y_position -= 20
        image = Image.open(image_path)
        aspect = image.height / float(image.width)
        c.drawInlineImage(image, 100, y_position - 200 * aspect, width=400, height=200 * aspect)
        return y_position - 200 * aspect - 30

    y_position = draw_image(upload['plot_path_decibels'].replace('\\', '/'), "Loudness Plot", c, y_position)
    y_position = draw_image(upload['waveform_plot_path'].replace('\\', '/'), "Waveform Plot", c, y_position)
    y_position = draw_image(upload['silence_speech_ratio_plot_path'].replace('\\', '/'), "Silence/Speech Ratio Plot", c, y_position)
    y_position = draw_image(upload['frequency_plot_path'].replace('\\', '/'), "Frequency Plot", c, y_position)
    y_position = draw_image(upload['plot_path_sr'].replace('\\', '/'), "Sampling Rate Plot", c, y_position)
    y_position = draw_image(upload['harmonicity_plot_path'].replace('\\', '/'), "Harmonicity Plot", c, y_position)

    c.save()

    # Save the PDF file to disk temporarily
    pdf_filename = f"{original_filename}_history.pdf"
    pdf_path = os.path.join("tmp", pdf_filename.replace(':', '_'))  # Replace illegal characters in filename
    try:
        with open(pdf_path, "wb") as f:
            f.write(pdf_buffer.getvalue())
    finally:
        # Close the pdf_buffer
        pdf_buffer.close()

    # Send the PDF file as a response
    response = send_file(pdf_path, mimetype='application/pdf', as_attachment=True)

    # Remove the PDF file from disk after sending
    try:
        os.remove(pdf_path)
    except Exception as e:
        print(f"Error while removing file: {e}")

    return response

@app.route('/delete_record/<int:record_id>')
def delete_record(record_id):
    user_id = session.get('user_id')
    if user_id is None:
        flash("You need to log in first")
        return redirect(url_for('login'))

    conn = pymysql.connect(
        host='localhost',
        user='root',
        password='',
        db='audio',
        charset='utf8mb4',
        cursorclass=pymysql.cursors.DictCursor
    )
    cursor = conn.cursor()

    # Fetch the record details to get the file paths
    cursor.execute('SELECT * FROM uploads WHERE audio_id = %s AND user_id = %s', (record_id, user_id))
    upload = cursor.fetchone()

    if not upload:
        flash("Record not found")
        conn.close()
        return redirect(url_for('history'))

    # Delete the files from the filesystem
    files_to_delete = [
        upload['plot_path_decibels'],
        upload['waveform_plot_path'],
        upload['silence_speech_ratio_plot_path'],
        upload['frequency_plot_path'],
        upload['plot_path_sr'],
        upload['harmonicity_plot_path'],
        os.path.join(app.config['UPLOAD_FOLDER'], upload['filename'])
    ]

    for file_path in files_to_delete:
        try:
            os.remove(file_path.replace('\\', '/'))
        except Exception as e:
            print(f"Error while removing file: {e}")

    # Delete the record from the database
    cursor.execute('DELETE FROM uploads WHERE audio_id = %s AND user_id = %s', (record_id, user_id))
    conn.commit()
    conn.close()

    flash("Record deleted successfully")
    return redirect(url_for('history'))


if __name__ == '__main__':
    app.run(debug=True)
