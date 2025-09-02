# CONVID24

If you're tired of incompatible and outdated video formats, CONVID24 is your solution!
It automatically detects video and audio codecs and runs the optimal FFmpeg commands, ensuring **visually and audibly lossless output** (at least for mortals), while **balancing file size and conversion time**.


## Features

- Convert multiple video formats to MP4:  
  `.mov`, `.avi`, `.mkv`, `.mpg`, `.mp4`, `.wmv`, `.flv`, `.webm`, `.vob`, `.m4v`, `.ts`, `.m2ts`, `.rm`, `.rmvb`, `.ogv`.
- Smart video encoding using **H.264 (libx264)** with the optimal (in the dev's opinion) CRF and preset combination.  
- Smart audio encoding to **AAC LC**, preserving quality based on original codec, bitrate, and channels.  
- Batch conversion for folders or multiple files.  
- Single-file and overall progress reporting.  


## Install & Run

1. **Clone the repository** by executing the following command in the terminal:

    git clone https://github.com/AngeloG97/CONVID24.git

2. **Install prerequisites:**

    - Python 3.10 or higher

    - FFmpeg installed and accessible in your system PATH

3. **Change to the CONVID24 directory and make the script executable (Linux, macOS only):**

    cd CONVID24

    chmod +x convid24.py

4. **Run the converter:**

    Right click > Run
