---
title: AI Tour Planning Bot
emoji: 🗺️
colorFrom: blue
colorTo: green
sdk: docker
app_port: 7860
---

# 🗺️ AI Tour Planning Bot

[![Live Demo](https://img.shields.io/badge/🚀_Live_Demo-Hugging_Face-yellow)](https://huggingface.co/spaces/ARDarvesh/AI-Tour-Planning-Bot)
[![GitHub](https://img.shields.io/badge/GitHub-Repository-blue)](https://github.com/ABDUL-RAHMAN-DARVESH/AI-Tour-Planning-Bot)
[![Python](https://img.shields.io/badge/Python-3.11+-green)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-Framework-red)](https://fastapi.tiangolo.com)

An intelligent AI-powered travel planning assistant that provides personalized trip recommendations, real-time weather updates, emergency SOS features, and comprehensive travel guidance for destinations across India.

## 🌟 Key Features

### 🎯 **Psychology-Aware Trip Planning**
- Considers meal times, energy levels, and rest periods
- Personalized itineraries based on traveler preferences
- Step-by-step daily schedules with optimal timing

### 🌤️ **Real-Time Information**
- Live weather forecasts and conditions
- Current news and travel advisories
- Up-to-date attraction information

### 🏞️ **Smart Recommendations**
- Safe, family-friendly attractions
- Local cuisine and restaurant suggestions
- Budget-conscious accommodation options
- Hidden gems and popular destinations

### 🆘 **Emergency SOS System**
- Instant emergency contact alerts
- Location-based emergency services
- WhatsApp integration for quick communication

### 🗺️ **Interactive Navigation**
- Turn-by-turn directions
- Distance and travel time calculations
- Multiple route options
- Public transport integration

## 🚀 Live Demo

**Try it now:** [https://huggingface.co/spaces/ARDarvesh/AI-Tour-Planning-Bot](https://huggingface.co/spaces/ARDarvesh/AI-Tour-Planning-Bot)

## 🛠️ Technology Stack

- **Backend:** FastAPI, Python 3.11+
- **AI/ML:** LangChain, Groq API, LangGraph
- **Database:** MongoDB Atlas
- **Frontend:** HTML, CSS, JavaScript
- **APIs:** OpenWeather, Unsplash, RapidAPI, News API
- **Deployment:** Docker, Hugging Face Spaces

## 📋 Prerequisites

- Python 3.11 or higher
- Docker (for containerized deployment)
- API keys for external services

## ⚡ Quick Start

### 1. Clone the Repository
```bash
git clone https://github.com/ABDUL-RAHMAN-DARVESH/AI-Tour-Planning-Bot.git
cd AI-Tour-Planning-Bot
```

### 2. Install Dependencies
```bash
pip install -r requirements.txt
```

### 3. Set Environment Variables
Create a `.env` file with your API keys:
```env
GROQ_API_KEY=your_groq_api_key
OPENWEATHER_API_KEY=your_openweather_key
UNSPLASH_ACCESS_KEY=your_unsplash_key
RAPIDAPI_KEY=your_rapidapi_key
MONGODB_URI=your_mongodb_connection_string
```

### 4. Run the Application
```bash
python app.py
```

Visit `http://localhost:7860` to access the web interface.

### 5. CLI Mode (Optional)
```bash
python app.py cli
```

## 🐳 Docker Deployment

```bash
# Build the image
docker build -t ai-tour-bot .

# Run the container
docker run -p 7860:7860 --env-file .env ai-tour-bot
```

## 🔧 Configuration

### Required Environment Variables

| Variable | Description | Required |
|----------|-------------|----------|
| `GROQ_API_KEY` | Groq AI API key for language model | ✅ |
| `OPENWEATHER_API_KEY` | Weather data API key | ✅ |
| `UNSPLASH_ACCESS_KEY` | Image search API key | ✅ |
| `RAPIDAPI_KEY` | Booking and places API key | ✅ |
| `MONGODB_URI` | Database connection string | ❌ |
| `NEWS_API_KEY` | News and updates API key | ❌ |
| `OPENROUTESERVICE_API_KEY` | Navigation API key | ❌ |

## 🎮 Usage Examples

### Trip Planning
```
"Plan a 3-day trip to Kerala"
"Weekend getaway to Goa under ₹10,000"
"Family trip to Rajasthan with kids"
```

### Weather Queries
```
"Weather in Mumbai tomorrow"
"Is it raining in Bangalore?"
"Best time to visit Manali"
```

### Place Information
```
"Best places in Ooty"
"Hotels near Gateway of India"
"Restaurants in Connaught Place"
```

## 🏗️ Project Structure

```
AI-Tour-Planning-Bot/
├── app.py                 # Main FastAPI application
├── trip_agent.py         # AI agent configuration
├── tool_integration.py   # Tool integrations
├── requirements.txt      # Python dependencies
├── Dockerfile           # Container configuration
├── frontend/            # Web interface files
│   ├── index.html
│   ├── tripset-full.html
│   └── config.js
├── tools/               # API integration tools
│   ├── weather.py
│   ├── places.py
│   ├── booking.py
│   ├── maps.py
│   ├── news.py
│   ├── images.py
│   └── sos.py
├── db/                  # Database utilities
│   └── mongo.py
└── prompts/             # AI prompts
    └── prompts.py
```

## 🤝 Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## 📝 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 👨💻 Author

**Abdul Rahman Darvesh**
- GitHub: [@ABDUL-RAHMAN-DARVESH](https://github.com/ABDUL-RAHMAN-DARVESH)
- LinkedIn: [Connect with me](https://linkedin.com/in/abdul-rahman-darvesh)

## 🙏 Acknowledgments

- [Groq](https://groq.com) for AI language model
- [OpenWeather](https://openweathermap.org) for weather data
- [Unsplash](https://unsplash.com) for beautiful travel images
- [MongoDB Atlas](https://mongodb.com/atlas) for database services
- [Hugging Face](https://huggingface.co) for hosting platform

## 📞 Support

If you encounter any issues or have questions:
1. Check the [Issues](https://github.com/ABDUL-RAHMAN-DARVESH/AI-Tour-Planning-Bot/issues) page
2. Create a new issue with detailed description
3. Contact the maintainer

---

⭐ **Star this repository if you found it helpful!**