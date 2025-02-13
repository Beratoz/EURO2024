# Euro2024 StatsBomb Analysis App

Welcome to the Euro2024 StatsBomb Analysis App – an interactive sports analytics project built with Streamlit using Hudl StatsBomb's free EURO 2024 data. This project is a labor of love and a fun way to practice analytics skills while exploring the performance of teams and players during Euro 2024.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Data Sources](#data-sources)
- [Technology Stack](#technology-stack)
- [Installation](#installation)
- [Usage](#usage)
- [Feedback and Contributions](#feedback-and-contributions)

## Overview

This interactive app aggregates and visualizes event-level data from EURO 2024 to derive insights about team tactics and individual performances. The project features a range of visualizations—from team passing networks and xG hot zones to detailed player report cards for goalkeepers, defenders, midfielders, and forwards.

I built this project for fun and to hone my sports analytics skills. While the app is fully deployed and operational, there’s still room for growth, and I welcome feedback and ideas for improvement.

## Features

- **Progressions into Final Third:** Visualizes passes that transition play into the attacking third.
- **Progressions Map:** Spatial analysis of progression actions.
- **Touch Comparison:** Side-by-side pitch visualizations comparing player touches.
- **Player Shot Map:** Displays the spatial distribution of a player's shots.
- **Team Shot Map:** Visualizes shot locations across the team.
- **Team Passing Network:** A network graph showing the interconnectivity of players through passes.
- **Team xG Hot Zones:** Heatmap of expected goals (xG) distribution across the pitch.
- **xG vs. Actual Goals:** A match-by-match comparison of a team’s xG versus actual goals scored.
- **Goalkeeper Report Card:** A detailed card summarizing key goalkeeper actions.
- **Defender Report Card:** A card displaying defensive metrics and tournament-wide percentiles for defenders.
- **Midfielder Report Card:** A card summarizing key offensive and defensive contributions of midfielders.
- **Forward Report Card:** A card comparing forwards on key metrics such as shots, goals, and passing.

## Data Sources

This app uses free data from Hudl StatsBomb's EURO 2024 dataset. The following tables are used:
- **Competitions:** Competition-level details.
- **Matches:** Match-level information.
- **Events:** Detailed event-level data, which forms the basis of all our analyses.
- **Full Tournament Events:** An aggregated version of all events in the tournament, used for computing tournament-wide percentiles.

## Technology Stack

- **Python** – Programming language
- **Streamlit** – For building interactive web applications
- **Pandas & NumPy** – For data manipulation and aggregation
- **Plotly Express & Plotly Graph Objects** – For interactive visualizations
- **mplsoccer** – For drawing football pitches and spatial visualizations
- **StatsBombpy** – For accessing StatsBomb’s free football data

## Installation

1. **Clone the Repository:**

   ```
   git clone https://github.com/Beratoz/EURO2024_Streamlit_App.git
   cd EURO2024_Streamlit_App
   ```

2. **Set Up a Virtual Environment (Optional but Recommended):**

   ```
   python -m venv venv
   source venv/bin/activate  # On Windows, use venv\Scripts\activate
   ```

3. **Install Dependencies:**

   ```
   pip install -r requirements.txt
   ```

## Usage

To run the app locally:

   ```
   streamlit run streamlit_app.py
   ```

## Feedback and Contributions

I built this project as a fun way to practice my sports analytics skills, and I'm always looking to improve it further. If you have feedback, suggestions, or would like to contribute, please feel free to open an issue or submit a pull request.

Connect with me on LinkedIn for further discussions!
