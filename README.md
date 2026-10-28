# YouTube to Doc

https://github.com/user-attachments/assets/4431d283-23c3-40eb-8c65-a20361a3e945

Turn any YouTube video into a comprehensive documentation link that AI coding tools and LLMs can easily index and understand.

## 🚀 Features

- **📺 YouTube Video Processing**: Extract video metadata, descriptions, and thumbnails
- **📝 Transcript Extraction**: Automatically extract video transcripts in multiple languages
- **🛟 Optional SearchApi Fallback**: [SearchApi](https://www.searchapi.io/) backs up video metadata and transcript extraction when existing providers fail. [Setup instructions](#optional-searchapi-fallback).
- **💬 Comments Integration**: Optional inclusion of video comments for additional context
- **🤖 AI-Friendly Output**: Generate structured documentation perfect for LLM consumption
- **⚡ Fast Processing**: Efficient video processing with rate limiting and caching
- **🌍 Multi-Language Support**: Support for transcripts in 9+ languages
- **📱 Responsive Design**: Beautiful, modern UI built with Tailwind CSS
- **🔧 API Access**: RESTful API for programmatic access
- **🐳 Docker Ready**: Easy deployment with Docker and Docker Compose

## 🛠️ Tech Stack

- **Backend**: FastAPI + Python 3.11+
- **Frontend**: Tailwind CSS + Jinja2 templates
- **Video Processing**: yt-dlp, pytube, youtube-transcript-api
- **Optional Fallback Provider**: [SearchApi](https://www.searchapi.io/) for YouTube video metadata and transcripts
- **Token Estimation**: tiktoken
- **Rate Limiting**: slowapi
- **Deployment**: Docker, Docker Compose

## 📦 Installation

### Option 1: Docker (Recommended)

```bash
# Clone the repository
git clone https://github.com/filiksyos/Youtube-to-Doc.git
cd youtubedoc

# Run with Docker Compose
docker-compose up -d
```

### Option 2: Local Installation

```bash
# Clone the repository
git clone https://github.com/filiksyos/Youtube-to-Doc.git
cd youtubedoc

# Install dependencies (using pnpm as specified in requirements)
pip install -r requirements.txt

# Run the application
uvicorn src.server.main:app --host 0.0.0.0 --port 8000 --reload
```

## 🚀 Usage

### Web Interface

1. Open your browser and navigate to `http://localhost:8000`
2. Enter a YouTube video URL
3. Configure processing options:
   - **Transcript Length**: Maximum characters to include
   - **Language**: Preferred transcript language
   - **Include Comments**: Whether to extract video comments
4. Click "Create Docs" to process the video

### API Usage

#### Process a Video

```bash
curl -X POST "http://localhost:8000/" \
  -H "Content-Type: application/x-www-form-urlencoded" \
  -d "input_text=https://www.youtube.com/watch?v=dQw4w9WgXcQ" \
  -d "max_transcript_length=10000" \
  -d "language=en" \
  -d "include_comments=false"
```

#### Python Example

```python
import requests

url = "http://localhost:8000/"
data = {
    "input_text": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
    "max_transcript_length": 10000,
    "language": "en",
    "include_comments": False
}

response = requests.post(url, data=data)
print(response.text)
```

## 🔧 Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

### Key Configuration Options

- `ALLOWED_HOSTS`: Comma-separated list of allowed hosts
- `YOUTUBE_API_KEY`: Optional YouTube Data API key for enhanced features
- `SEARCHAPI_API_KEY`: Optional server-side SearchApi key for metadata and transcript fallback
- `OPENAI_API_KEY`: Optional OpenAI API key for AI-enhanced processing
- `RATE_LIMIT_PER_MINUTE`: Number of requests per minute per IP

### Optional SearchApi Fallback

[SearchApi](https://www.searchapi.io/) provides the optional YouTube metadata and
transcript fallback. It is disabled by default and does not replace the existing
providers. To enable it, add your SearchApi key to the server's private `.env`:

```dotenv
SEARCHAPI_API_KEY=your_searchapi_api_key
```

Alternatively, set `SEARCHAPI_API_KEY` directly in your server's environment.
Restart the server after changing it. Leave it blank to keep SearchApi disabled.
Docker Compose passes this
variable through; for `docker run`, supply it with `--env-file .env` (keep that
file private). Never commit the key or include it in frontend code.

Existing providers stay first:

- **Metadata:** yt-dlp → pytube → SearchApi's `youtube_video` engine → minimal metadata.
- **Transcripts:** youtube-transcript-api (including its existing language fallback)
  → SearchApi's `youtube_transcripts` engine → no transcript.

SearchApi is called only when the existing providers fail, are unavailable, or
return an empty transcript. It receives the video ID and, for transcripts, the
preferred language. If SearchApi reports that language unavailable and lists other
tracks, the app tries the first available alternative once and records its language.
The same transcript length limit and truncation marker apply to both providers.
Comments are unchanged; SearchApi is not used for comments.

Enabling this fallback can consume your SearchApi credits: each processing attempt
can make one metadata request and up to two transcript requests. Successful primary
providers make no SearchApi requests. Authentication, quota, timeout, malformed
response, and service errors degrade to the existing minimal metadata / missing
transcript behavior, without automatic retries. Requests have a 5-second connection
timeout and 20-second read timeout. Credentials use the Authorization header, not
the URL, and provider error bodies are not logged or returned to users.

See the official [YouTube Video API](https://www.searchapi.io/docs/youtube-video)
and [YouTube Transcripts API](https://www.searchapi.io/docs/youtube-transcripts)
documentation. The automated tests use mocked responses and require no key or
credits. A live smoke test requires a separately configured server key and will
consume requests; it is not part of the test suite.

### AWS S3 Integration (for cloud documentation links)

To publish generated docs to S3 and show "View Documentation" and "Copy Documentation Link" buttons (as used on `youtubetodoc.com`), configure an S3 bucket and environment variables.

1) Create an S3 bucket
- Region: choose your region (e.g., eu-north-1)
- Object Ownership: ACLs disabled (Bucket owner enforced)
- Public access: turn OFF “Block all public access” if you want public S3 URLs

2) Add a read-only bucket policy (recommended to scope to `docs/`):
```json
{
  "Version": "2012-10-17",
  "Statement": [
    {
      "Sid": "AllowPublicReadDocs",
      "Effect": "Allow",
      "Principal": "*",
      "Action": "s3:GetObject",
      "Resource": "arn:aws:s3:::YOUR_BUCKET/docs/*"
    }
  ]
}
```

3) Set environment variables in `.env`:
```bash
AWS_S3_BUCKET=YOUR_BUCKET
AWS_ACCESS_KEY_ID=your_access_key
AWS_SECRET_ACCESS_KEY=your_secret_key
AWS_REGION=eu-north-1
```

4) Restart the server so `.env` is reloaded.

Notes
- The app auto-detects the bucket's real region to construct the correct URL, avoiding PermanentRedirect.
- If you prefer not to expose public S3, keep Block Public Access on and serve via CloudFront instead.

### Proxy Configuration (Cloud Deployment Only)

**⚠️ Note: This is only needed for cloud deployment (Render, Heroku, AWS, etc.). Local development works without proxies.**

When deploying to cloud providers, YouTube often blocks requests from cloud IPs, causing `IpBlocked` or `RequestBlocked` errors. To fix this, configure rotating residential proxies:

1) **Sign up for Webshare** (recommended by `youtube-transcript-api`):
   - Visit [webshare.io](https://www.webshare.io) and create an account
   - Purchase a "Rotating Residential" plan (NOT "Proxy Server" or "Static Residential")
   - Go to Proxies → Rotating Residential → Proxy Settings to get your credentials

2) **Set environment variables** in your deployment:
```bash
# Webshare credentials (base username/password)
YTA_WEBSHARE_USERNAME=your_webshare_username
YTA_WEBSHARE_PASSWORD=your_webshare_password
YTA_WEBSHARE_LOCATIONS=jp,kr,tw  # optional: filter by countries

# Proxy URLs for yt-dlp/pytube (use specific pod usernames from your proxy list)
YTA_HTTP_PROXY=http://your_pod_username:your_password@p.webshare.io:80
YTA_HTTPS_PROXY=http://your_pod_username:your_password@p.webshare.io:80
```

3) **Alternative**: Use any HTTP/HTTPS proxy provider:
```bash
YTA_HTTP_PROXY=http://user:pass@proxy-host:port
YTA_HTTPS_PROXY=https://user:pass@proxy-host:port
```

The app will automatically route YouTube API calls through the proxy when these variables are set.

## 📋 Supported YouTube URL Formats

- `https://www.youtube.com/watch?v=VIDEO_ID`
- `https://youtu.be/VIDEO_ID`
- `https://www.youtube.com/embed/VIDEO_ID`
- `https://www.youtube.com/v/VIDEO_ID`

## 🌍 Supported Languages

- English (en)
- Spanish (es)
- French (fr)
- German (de)
- Italian (it)
- Portuguese (pt)
- Japanese (ja)
- Korean (ko)
- Chinese (zh)

## 🔄 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/` | Home page with video processing form |
| `POST` | `/` | Process a YouTube video |
| `GET` | `/video/{video_id}` | Get processing form for specific video |
| `POST` | `/video/{video_id}` | Process specific video |
| `GET` | `/api` | API documentation |
| `GET` | `/health` | Health check endpoint |

## 📊 Rate Limits

- Main endpoint: 10 requests per minute per IP
- Video-specific endpoint: 5 requests per minute per IP
- Streaming processing endpoint: 5 requests per minute per IP (including cache checks)

These are per-IP limits, not an account-wide SearchApi spending cap. Monitor your
provider quota before enabling the optional fallback on a public deployment.

## 🐳 Docker Deployment

### Development

```bash
docker-compose up -d
```

### Production

```bash
# Build and run
docker build -t youtubedoc .
docker run -p 8000:8000 \
  -e ALLOWED_HOSTS=yourdomain.com \
  -e DEBUG=False \
  youtubedoc
```

## 📝 Example Output

The generated documentation includes:

- **Video Metadata**: Title, duration, view count, channel info
- **Description**: Full video description
- **Transcript**: Complete video transcript with timestamps
- **Comments**: Top video comments (if enabled)
- **Token Estimation**: Estimated token count for LLM usage

## 🧪 Testing

Install test dependencies and run the mocked, network-free tests:

```bash
python -m pip install -r requirements.txt pytest
python -m pytest tests/
python -m compileall -q src tests
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📄 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🙏 Acknowledgments

- Inspired by [Gittodoc](https://github.com/filiksyos/gittodoc) for the overall architecture and design
- Built with [FastAPI](https://fastapi.tiangolo.com/) for the web framework
- Uses [yt-dlp](https://github.com/yt-dlp/yt-dlp) for robust YouTube video processing
- Styled with [Tailwind CSS](https://tailwindcss.com/) for the modern UI

## 📞 Support

If you encounter any issues or have questions:

1. Check the [API documentation](http://localhost:8000/api) 
2. Review the [issues page](https://github.com/your-username/youtubedoc/issues)
3. Create a new issue if needed

---

**Made with ❤️ for the AI and developer community** 
