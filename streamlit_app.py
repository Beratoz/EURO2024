import streamlit as st
from statsbombpy import sb
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch
import plotly.express as px

# Configure Streamlit
st.set_page_config(page_title="Euro 2024 Analysis", layout="wide")
st.title("Euro 2024 StatsBomb Analysis ⚽")

# Configure StatsBombpy to use free data
sb.login = lambda: None  # Bypass credential check for open data

# Cache competitions data
@st.cache_data
def load_competitions():
    return sb.competitions()

# Cache matches data for Euro2024
@st.cache_data
def load_matches():
    return sb.matches(competition_id=55, season_id=282)

# Cache events data for a tuple of match IDs
@st.cache_data
def load_events_for_matches(match_ids):
    events_list = []
    for m in match_ids:
        events_m = sb.events(match_id=m)
        events_list.append(events_m)
    if events_list:
        events = pd.concat(events_list, ignore_index=True)
    else:
        events = pd.DataFrame()
    return events

def main():
    # Load competitions and matches data
    competitions = load_competitions()
    matches = load_matches()
    
    # Create a sorted list of all teams (ignoring NaNs)
    all_teams = pd.concat([matches['home_team'], matches['away_team']]).unique()
    all_teams = sorted([team for team in all_teams if pd.notna(team)])
    
    # Sidebar: Select Team
    st.sidebar.header("Filters")
    team = st.sidebar.selectbox("Select Team", all_teams)
    
    # Filter matches for the selected team
    team_matches = matches[(matches['home_team'] == team) | (matches['away_team'] == team)]
    if team_matches.empty:
        st.error("No matches found for the selected team.")
        return
    
    # Create match options for filtering
    if 'match_date' in team_matches.columns:
        # Ensure match_date is in datetime format
        team_matches['match_date'] = pd.to_datetime(team_matches['match_date'], errors='coerce')
        match_options = team_matches.apply(
            lambda row: f"{row['match_date'].date()} - {row['home_team']} vs {row['away_team']}",
            axis=1
        ).tolist()
    else:
        match_options = team_matches.apply(
            lambda row: f"Match {row['match_id']}: {row['home_team']} vs {row['away_team']}",
            axis=1
        ).tolist()
    
    # Create a dictionary to map the match option strings to match IDs
    match_dict = dict(zip(match_options, team_matches['match_id']))
    
    # Sidebar: Match Filter
    st.sidebar.header("Match Filter")
    selected_match_options = st.sidebar.multiselect(
        "Select match(es)",
        options=match_options,
        default=match_options  # Default selects all available matches
    )
    
    if not selected_match_options:
        st.error("Please select at least one match.")
        return
    selected_match_ids = [match_dict[s] for s in selected_match_options]
    
    # Sidebar: Choose Visualization
    viz_option = st.sidebar.radio(
        "Select Visualization",
        ("Progressions into Final Third", "Touch Comparison")
    )
    
    # Load events for the selected match(es)
    events = load_events_for_matches(tuple(selected_match_ids))
    
    if events.empty:
        st.error("No event data available for the selected match(es).")
        return
    
    # Process event data: extract coordinate information from the location fields
    events[['x', 'y']] = events['location'].apply(
        lambda loc: pd.Series(loc if isinstance(loc, list) else [None, None])
    )
    events[['pass_end_x', 'pass_end_y']] = events['pass_end_location'].apply(
        lambda loc: pd.Series(loc if isinstance(loc, list) else [None, None])
    )
    events[['carry_end_x', 'carry_end_y']] = events['carry_end_location'].apply(
        lambda loc: pd.Series(loc if isinstance(loc, list) else [None, None])
    )
    
    # Display the selected visualization
    if viz_option == "Progressions into Final Third":
        st.header(f"{team} Progressions into Final Third")
        plot_progressions(events, team)
    
    elif viz_option == "Touch Comparison":
        st.header("Touch Comparison")
        # For touch comparison, allow selection of two players from the available events
        players = sorted(events['player'].dropna().unique())
        if not players:
            st.error("No player data available in the selected match(es).")
            return
        player1 = st.sidebar.selectbox("Select Player 1", players)
        players_for_player2 = [p for p in players if p != player1]
        if not players_for_player2:
            st.error("Not enough players available for comparison.")
            return
        player2 = st.sidebar.selectbox("Select Player 2", players_for_player2)
        plot_touch_comparison(events, player1, player2)

def plot_progressions(events, team):
    """
    Uses Plotly Express to create an interactive horizontal bar chart showing
    the number of passes that progress into the final third.
    """
    # Filter for passes:
    # - The event is a pass from the selected team
    # - The pass starts before x=80 and ends after x=80 (assuming StatsBomb pitch dimensions)
    # - The pass was completed (pass_outcome is NaN)
    f3rd_passes = events[
        (events.team == team) &
        (events.type == "Pass") &
        (events.x < 80) &
        (events.pass_end_x > 80) &
        events.pass_outcome.isna()
    ]
    
    counts = f3rd_passes.groupby('player').size().reset_index(name='count')
    counts = counts.sort_values('count')
    
    fig = px.bar(
        counts,
        x='count',
        y='player',
        orientation='h',
        title=f"Progressions into Final Third for {team}",
        labels={'count':'Passes into Final Third', 'player':'Player'},
        color_discrete_sequence=["steelblue"]
    )
    st.plotly_chart(fig, use_container_width=True)

def plot_touch_comparison(events, player1, player2):
    """
    Uses mplsoccer to create side-by-side pitch plots showing the touch locations for two players.
    """
    player1_df = events[events.player == player1]
    player2_df = events[events.player == player2]
    
    fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(20, 10))
    pitch = Pitch(pitch_type='statsbomb', line_zorder=2, linewidth=2)
    
    # Draw pitch and player 1 touches
    pitch.draw(ax=ax1)
    ax1.scatter(player1_df.x, player1_df.y, color='red', s=100, alpha=0.7)
    ax1.set_title(f"Touches for {player1}", fontsize=16)
    
    # Draw pitch and player 2 touches
    pitch.draw(ax=ax2)
    ax2.scatter(player2_df.x, player2_df.y, color='blue', s=100, alpha=0.7)
    ax2.set_title(f"Touches for {player2}", fontsize=16)
    
    st.pyplot(fig)

if __name__ == "__main__":
    main()
