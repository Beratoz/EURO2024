import streamlit as st
from statsbombpy import sb
import pandas as pd
import matplotlib.pyplot as plt
from mplsoccer import Pitch, VerticalPitch
import plotly.express as px
from highlight_text import ax_text
import matplotlib.patheffects as path_effects

# Configure Streamlit
st.set_page_config(page_title="Euro 2024 Analysis", layout="wide")
st.title("Euro 2024 StatsBomb Analysis ⚽")

st.markdown(
    """
    ### About This App
    
    Hi, I'm **Berat Ozmen** and I'm a sports analytics fan. I built this app purely for fun. You can connect with me on [LinkedIn](https://www.linkedin.com/in/beratozmen/).
    
    This app uses [StatsBomb's free data](https://statsbomb.com/news/statsbomb-release-free-euro-2024-data/) for Euro 2024 analysis.
    """,
    unsafe_allow_html=True
)


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
    
    # Build a sorted list of all teams (ignoring NaN)
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
    
    # Build match options using date (if available) and teams
    if 'match_date' in team_matches.columns:
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
    
    # Map the match option string to match ID
    match_dict = dict(zip(match_options, team_matches['match_id']))
    
    # Sidebar: Match Filter (default is empty = all matches)
    st.sidebar.header("Match Filter")
    selected_match_options = st.sidebar.multiselect(
        "Select match(es) (leave empty to include all matches)",
        options=match_options,
        default=[]
    )
    if not selected_match_options:
        # If none selected, use all match IDs for this team
        selected_match_ids = list(match_dict.values())
    else:
        selected_match_ids = [match_dict[s] for s in selected_match_options]
    
    # Sidebar: Choose Visualization (order: Progressions into Final Third, Progressions Map, Touch Comparison etc.)
    viz_option = st.sidebar.radio(
    "Select Visualization",
    ("Progressions into Final Third", "Progressions Map", "Player Shot Map", "Goalkeeper Report Card", "Touch Comparison", "Team Shot Map")
)

    # Load events for the selected match(es)
    events = load_events_for_matches(tuple(selected_match_ids))
    if events.empty:
        st.error("No event data available for the selected match(es).")
        return
    
    # Process event data: extract coordinate information from location fields
    events[['x', 'y']] = events['location'].apply(
        lambda loc: pd.Series(loc if isinstance(loc, list) else [None, None])
    )
    events[['pass_end_x', 'pass_end_y']] = events['pass_end_location'].apply(
        lambda loc: pd.Series(loc if isinstance(loc, list) else [None, None])
    )
    events[['carry_end_x', 'carry_end_y']] = events['carry_end_location'].apply(
        lambda loc: pd.Series(loc if isinstance(loc, list) else [None, None])
    )
    
    # Ensure extra column for hover data exists; we only need "position"
    if 'position' not in events.columns:
        events['position'] = "N/A"
    
    # Display the selected visualization
    if viz_option == "Progressions into Final Third":
        st.header(f"{team} Progressions into Final Third")
        plot_progressions(events, team)
    
    elif viz_option == "Progressions Map":
        st.header("Progressions Map")
        # Filter progression events for passes and carries for this team
        f3rd_passes = events[
            (events.team == team) &
            (events.type == "Pass") &
            (events.x < 80) &
            (events.pass_end_x > 80) &
            events.pass_outcome.isna()
        ]
        f3rd_carries = events[
            (events.team == team) &
            (events.type == "Carry") &
            (events.x < 80) &
            (events.carry_end_x > 80)
        ]
        # Create a list of players who have at least one progression action
        players_progressions = pd.concat([f3rd_passes['player'], f3rd_carries['player']]).dropna().unique()
        players_progressions = sorted(players_progressions)
        if not players_progressions:
            st.error("No progression events available for the selected team/matches.")
            return
        selected_player = st.sidebar.selectbox("Select Player for Progression Map", players_progressions)
        plot_progressions_map(events, team, selected_player)
    
    elif viz_option == "Touch Comparison":
        st.header("Touch Comparison")
        # For Touch Comparison, allow selection of two players from available events
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

    elif viz_option == "Team Shot Map":
        st.header(f"{team} Shot Map")
        plot_team_shot_map(events, team)
    
    elif viz_option == "Player Shot Map":
        st.header("Player Shot Map")
        # Gather all players that have shot events in the current events data
        players_shots = events[events.type == "Shot"].player.dropna().unique().tolist()
        if not players_shots:
            st.error("No shot data available for the selected match(es).")
            return
        selected_player = st.sidebar.selectbox("Select Player for Shot Map", sorted(players_shots))
        plot_player_shot_map(events, selected_player)

    elif viz_option == "Goalkeeper Report Card":
        st.header("Goalkeeper Report Card")
        # Use the position field to list only goalkeepers.
        gk_list = events[events.position == "Goalkeeper"].player.dropna().unique().tolist()
        if not gk_list:
            st.error("No goalkeeper data available in the selected match(es).")
            return
        selected_gk = st.sidebar.selectbox("Select Goalkeeper", sorted(gk_list))
        plot_goalkeeper_report_card(events, selected_gk)



def plot_progressions(events, team):
    """
    Creates an interactive horizontal stacked bar chart using Plotly Express that
    shows the total (stacked) count of passes and carries progressing into the final third.
    The players are ordered in descending order of total count.
    Hover data includes only the player's position.
    """
    # Filter for passes: start before x=80 and end after x=80, and completed passes
    pass_events = events[
        (events.team == team) &
        (events.type == "Pass") &
        (events.x < 80) &
        (events.pass_end_x > 80) &
        events.pass_outcome.isna()
    ]
    # Filter for carries: start before x=80 and end after x=80
    carry_events = events[
        (events.team == team) &
        (events.type == "Carry") &
        (events.x < 80) &
        (events.carry_end_x > 80)
    ]
    
    # Aggregate counts per player
    pass_counts = pass_events.groupby("player").size().reset_index(name="count")
    carry_counts = carry_events.groupby("player").size().reset_index(name="count")
    
    # Get additional player info (only position is needed for hover)
    player_info = events.groupby("player").agg({
        "position": "first"
    }).reset_index()
    
    # Merge player info with counts
    pass_counts = pass_counts.merge(player_info, on="player", how="left")
    carry_counts = carry_counts.merge(player_info, on="player", how="left")
    
    # Add a column to denote the type of action
    pass_counts["action"] = "Pass"
    carry_counts["action"] = "Carry"
    
    # Combine both dataframes
    df = pd.concat([pass_counts, carry_counts], ignore_index=True)
    
    # Determine descending order of total (Pass+Carry) counts per player
    total_counts = df.groupby("player")["count"].sum().reset_index()
    total_counts = total_counts.sort_values("count", ascending=False)
    ordered_players = total_counts["player"].tolist()
    
    # Create the stacked bar chart with hover data (only position is shown)
    fig = px.bar(
        df,
        x="count",
        y="player",
        color="action",
        orientation="h",
        title=f"Progressions into Final Third for {team}",
        labels={"count": "Count", "player": "Player", "action": "Action"},
        hover_data={"position": True},
        category_orders={"player": ordered_players},
        color_discrete_map={"Pass": "steelblue", "Carry": "red"}
    )

    fig.update_layout(barmode="stack")
    st.plotly_chart(fig, use_container_width=True)

def plot_progressions_map(events, team, player_name):
    """
    Creates a pitch map using mplsoccer that shows progression passes and carries
    for the selected player.
    """
    # Filter progression passes and carries for the selected team and player
    f3rd_passes = events[
        (events.team == team) &
        (events.type == "Pass") &
        (events.x < 80) &
        (events.pass_end_x > 80) &
        events.pass_outcome.isna() &
        (events.player == player_name)
    ]
    f3rd_carries = events[
        (events.team == team) &
        (events.type == "Carry") &
        (events.x < 80) &
        (events.carry_end_x > 80) &
        (events.player == player_name)
    ]
    
    # Set up the pitch
    pitch = Pitch(pitch_type='statsbomb', pitch_color='white', line_zorder=2, line_color='black')
    fig, ax = pitch.draw(figsize=(16, 11), constrained_layout=True, tight_layout=False)
    fig.set_facecolor('white')
    
    # Define colors for passes and carries
    pass_colour = "blue"
    carry_colour = "red"
    
    # Plot the passes (if available)
    if not f3rd_passes.empty:
        pitch.arrows(
            f3rd_passes.x, f3rd_passes.y,
            f3rd_passes.pass_end_x, f3rd_passes.pass_end_y,
            width=3, headwidth=8, headlength=5,
            color=pass_colour, ax=ax, zorder=2, label="Pass"
        )
    # Plot the carries (if available)
    if not f3rd_carries.empty:
        pitch.arrows(
            f3rd_carries.x, f3rd_carries.y,
            f3rd_carries.carry_end_x, f3rd_carries.carry_end_y,
            width=3, headwidth=8, headlength=5,
            color=carry_colour, ax=ax, zorder=2, label="Carry"
        )
    
    # Add the legend and title
    ax.legend(facecolor='white', handlelength=5, edgecolor='None', fontsize=20, loc='best')
    ax.set_title(f'{player_name} Progressions into Final 3rd: Euros Final', fontsize=30, color='black')
    
    st.pyplot(fig)

def plot_touch_comparison(events, player1, player2):
    """
    Creates a grid of vertical pitches (using mplsoccer) with heatmaps showing the 
    percentage distribution of touches for two players.
    """
    # Filter events for each player
    player1_df = events[events.player == player1]
    player2_df = events[events.player == player2]
    
    # Define path effects for text annotation
    path_eff = [path_effects.Stroke(linewidth=3, foreground='black'),
                path_effects.Normal()]
    
    # Define a colormap (you can adjust as needed)
    cmap = "Reds"
    
    # Create a VerticalPitch instance and grid of two pitches
    pitch = VerticalPitch(pitch_type='statsbomb', line_zorder=2, line_color='#000000', linewidth=2, half=False)
    fig, axs = pitch.grid(nrows=1, ncols=2,
                          figheight=16,
                          grid_width=0.65,
                          endnote_height=0.03, endnote_space=0.05,
                          axis=False, title_space=0.02, title_height=0.06, grid_height=0.8)
    
    # Compute binned statistics for player touches (normalize=True gives percentages)
    bin_statistic1 = pitch.bin_statistic(player1_df.x, player1_df.y, statistic='count', bins=(6, 4), normalize=True)
    bin_statistic2 = pitch.bin_statistic(player2_df.x, player2_df.y, statistic='count', bins=(6, 4), normalize=True)
    
    # Determine common vmax for both heatmaps
    vmax1 = bin_statistic1['statistic'].max()
    vmax2 = bin_statistic2['statistic'].max()
    vmax = vmax1 if vmax1 > vmax2 else vmax2
    vmin = 0  # set vmin to zero
    
    # Plot heatmap for player1
    heatmap1 = pitch.heatmap(bin_statistic1, ax=axs['pitch'][0], cmap=cmap, vmax=vmax, vmin=vmin)
    # Add percentage annotations for each zone
    annotate1 = pitch.label_heatmap(bin_statistic1, color='white',
                                    path_effects=path_eff, fontsize=50, ax=axs['pitch'][0],
                                    str_format='{:.0%}',
                                    ha='center', va='center',
                                    exclude_zeros=True)
    # Add player name to the top of the heatmap for player1
    ax_text(0, 125, f'{player1}: Touches', ha='left', c='black', va='center', fontsize=45, ax=axs['pitch'][0], style='italic')
    
    # Plot heatmap for player2
    heatmap2 = pitch.heatmap(bin_statistic2, ax=axs['pitch'][1], cmap=cmap, vmax=vmax, vmin=vmin)
    # Add percentage annotations for each zone
    annotate2 = pitch.label_heatmap(bin_statistic2, color='white',
                                    path_effects=path_eff, fontsize=50, ax=axs['pitch'][1],
                                    str_format='{:.0%}',
                                    ha='center', va='center',
                                    exclude_zeros=True)
    # Add player name to the top of the heatmap for player2
    ax_text(0, 125, f'{player2}: Touches', ha='left', c='black', va='center', fontsize=45, ax=axs['pitch'][1], style='italic')
    
    st.pyplot(fig)

def plot_team_shot_map(events, team):
    """
    Creates a shot map for the selected team using all the shot events
    in the filtered match(es). Shots are plotted on a full pitch,
    with marker sizes scaled by shot_statsbomb_xg. Goal shots are highlighted
    in green (using a football marker) and non-goal shots in red.
    """
    # Filter shot events for the selected team
    team_shots = events[(events.team == team) & (events.type == "Shot")]
    
    if team_shots.empty:
        st.error("No shot data available for the selected team/matches.")
        return
    
    # Set up a full pitch using mplsoccer's Pitch
    pitch = Pitch(pitch_type='statsbomb', pitch_color='white', line_color='black', line_zorder=2)
    fig, ax = pitch.draw(figsize=(12, 8))
    
    # Separate shots that resulted in goals from other shots
    goal_shots = team_shots[team_shots.shot_outcome == "Goal"]
    non_goal_shots = team_shots[team_shots.shot_outcome != "Goal"]
    
    # Plot non-goal shots
    # Plot non-goal shots
    pitch.scatter(
        non_goal_shots.x, non_goal_shots.y,
        s=non_goal_shots.shot_statsbomb_xg * 1000,
        c='red',
        alpha=0.6,
        label='Shot (Missed/Saved)',
        ax=ax
    )

    # Plot goal shots
    pitch.scatter(
        goal_shots.x, goal_shots.y,
        s=goal_shots.shot_statsbomb_xg * 1000,
        c='green',
        alpha=0.9,
        marker='football',
        label='Goal',
        ax=ax
    )

    
    # Add legend and title
    ax.legend(facecolor='white', edgecolor='none', fontsize=14, loc='upper right')
    ax.set_title(f"{team} Shot Map", fontsize=20)
    st.pyplot(fig)

def plot_player_shot_map(events, player_name):
    """
    Creates a shot map for the selected player using all the shot events
    for that player. Shots are plotted on a half pitch using VerticalPitch,
    with marker sizes scaled by shot_statsbomb_xg.
    Non-goal shots are shown in red, and goals are shown in green.
    """
    # Filter shot events for the selected player, ignoring penalty shots
    player_shots = events[
        (events.player == player_name) &
        (events.type == "Shot") &
        (events.shot_type != "Penalty")
    ]
    if player_shots.empty:
        st.error("No shot data available for this player.")
        return

    # Separate shots that resulted in goals from non-goal shots
    goal_shots = player_shots[player_shots.shot_outcome == "Goal"]
    non_goal_shots = player_shots[player_shots.shot_outcome != "Goal"]

    # Set up the half pitch using VerticalPitch
    pitch = VerticalPitch(pitch_type='statsbomb', half=True, pad_bottom=-11)
    fig, ax = pitch.draw(figsize=(12, 10))

    # Plot non-goal shots with red markers (using the 'c' parameter for color)
    pitch.scatter(
        non_goal_shots.x, non_goal_shots.y,
        s=non_goal_shots.shot_statsbomb_xg * 1000,
        c='red',
        alpha=0.6,
        label='Shot (Missed/Saved)',
        ax=ax
    )

    # Plot goal shots with green markers (using the 'c' parameter)
    pitch.scatter(
        goal_shots.x, goal_shots.y,
        s=goal_shots.shot_statsbomb_xg * 1000,
        c='green',
        alpha=0.9,
        marker='football',  # 'football' marker works if your mplsoccer version supports it
        label='Goal',
        ax=ax
    )

    # Add a legend and a title
    ax.legend(facecolor='white', handlelength=5, edgecolor='None', fontsize=20, loc='best')
    ax.set_title(f"{player_name} Shot Map", fontsize=20)
    st.pyplot(fig)

def plot_goalkeeper_report_card(events, goalkeeper_name):
    """
    Displays a report card for the selected goalkeeper based on key event metrics,
    and then plots a passing map for the goalkeeper.
    
    The report card shows these metrics (computed as counts of events):
      - Pass
      - Ball Receipt*
      - Carry
      - Ball Recovery
      - Bad Behaviour
      - Injury Stoppage
      - Foul Won
      
    Then, below the metrics, a pitch is drawn with arrows representing the goalkeeper's passes.
    """
    # Filter events for the selected goalkeeper.
    gk_events = events[events.player == goalkeeper_name]
    
    # Define the list of event types to include (excluding the ambiguous "Goal Keeper" type).
    event_list = [
        "Pass", 
        "Ball Receipt*", 
        "Carry", 
        "Ball Recovery", 
        "Bad Behaviour", 
        "Injury Stoppage", 
        "Foul Won"
    ]
    
    # Compute counts for each event type.
    counts = {event: gk_events[gk_events.type == event].shape[0] for event in event_list}
    
    st.markdown(f"### Goalkeeper Report Card: {goalkeeper_name}")
    
    # Display the metrics in two rows using Streamlit's columns.
    # (Since we have 7 metrics, we'll show 4 in the first row and 3 in the second row.)
    row1, row2 = st.columns(4), st.columns(3)
    for i, event in enumerate(event_list):
        if i < 4:
            row1[i].metric(label=event, value=counts[event])
        else:
            row2[i - 4].metric(label=event, value=counts[event])
    
    st.markdown("#### Passing Map")
    
    # Filter for passes made by the goalkeeper.
    gk_passes = gk_events[gk_events.type == "Pass"]
    
    if gk_passes.empty:
        st.info("No passing data available for this goalkeeper in the selected match(es).")
    else:
        # Set up a full pitch using mplsoccer's Pitch.
        from mplsoccer import Pitch  # ensure this is imported at the top of your file
        pitch = Pitch(pitch_type='statsbomb', pitch_color='white', line_color='black', line_zorder=2)
        fig, ax = pitch.draw(figsize=(12, 8))
        
        # Plot each pass as an arrow from the starting coordinates to the pass end.
        # (Make sure that your events DataFrame already has the columns 'x', 'y', 'pass_end_x', 'pass_end_y'.)
        for _, row in gk_passes.iterrows():
            # Only plot if the pass has an end location
            if pd.notna(row['pass_end_x']) and pd.notna(row['pass_end_y']):
                pitch.arrows(
                    row['x'], row['y'], row['pass_end_x'], row['pass_end_y'],
                    width=2,
                    headwidth=8,
                    headlength=5,
                    color="orange",
                    ax=ax,
                    zorder=2
                )
        
        ax.set_title(f"{goalkeeper_name} Passing Map", fontsize=20)
        st.pyplot(fig)

if __name__ == "__main__":
    main()