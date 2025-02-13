import streamlit as st
from statsbombpy import sb
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
from mplsoccer import Pitch, VerticalPitch
import plotly.express as px
from highlight_text import ax_text
import matplotlib.patheffects as path_effects
from scipy.stats import percentileofscore
import plotly.graph_objects as go

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

@st.cache_data
def load_full_competition_events():
    # This loads all events for the competition (tournament-level data).
    comp_events = sb.competition_events(
         country='Europe',
         division='UEFA Euro',
         season='2024',
         gender="male"
    )
    
    # Extract coordinate columns in one go (to avoid fragmentation)
    coords = comp_events['location'].apply(pd.Series).rename(columns={0: 'x', 1: 'y'})
    pass_end_coords = comp_events['pass_end_location'].apply(pd.Series).rename(columns={0: 'pass_end_x', 1: 'pass_end_y'})
    carry_end_coords = comp_events['carry_end_location'].apply(pd.Series).rename(columns={0: 'carry_end_x', 1: 'carry_end_y'})
    comp_events = pd.concat([comp_events, coords, pass_end_coords, carry_end_coords], axis=1).copy()
    
    return comp_events


def main():
    # Load competitions and matches data
    competitions = load_competitions()
    matches = load_matches()

    full_comp_events = load_full_competition_events()
    
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
    ("Progressions into Final Third", "Progressions Map", "Touch Comparison", "Player Shot Map",
     "Team Shot Map", "Team Passing Network", "Team xG Hot Zones", "xG vs. Actual Goals", "Goalkeeper Report Card", 
     "Defender Report Card", "Midfielder Report Card", "Forward Report Card")
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
        else:
            selected_gk = st.sidebar.selectbox("Select Goalkeeper", sorted(gk_list))
            plot_goalkeeper_report_card(events, selected_gk, full_goalkeeper_events=full_comp_events)


    elif viz_option == "Defender Report Card":
        st.header("Defender Report Card")
        # Use common defender positions to filter defenders from the currently filtered events,
        # but note that the percentile calculations will come from full_comp_events.
        defender_positions = ["Center Back", "Left Center Back", "Right Center Back", "Left Wing Back", "Right Wing Back"]
        defenders_subset = events[events.position.isin(defender_positions)]
        defender_list = defenders_subset.player.dropna().unique().tolist()
        if not defender_list:
            st.error("No defender data available in the selected match(es).")
        else:
            selected_defender = st.sidebar.selectbox("Select Defender", sorted(defender_list))
            plot_defender_report_card(events, selected_defender, full_defender_events=full_comp_events)

    elif viz_option == "Midfielder Report Card":
        st.header("Midfielder Report Card")
        # Use the updated midfielder_positions list to filter midfielders.
        midfielder_positions = [
            "Center Attacking Midfield",
            "Center Defensive Midfield",
            "Left Attacking Midfield",
            "Left Center Midfield",
            "Left Defensive Midfield",
            "Left Midfield",
            "Right Attacking Midfield",
            "Right Center Midfield",
            "Right Defensive Midfield",
            "Right Midfield",
            "Left Wing",
            "Right Wing"
        ]
        midfielders_subset = events[events.position.isin(midfielder_positions)]
        midfielder_list = midfielders_subset.player.dropna().unique().tolist()
        if not midfielder_list:
            st.error("No midfielder data available in the selected match(es).")
        else:
            selected_midfielder = st.sidebar.selectbox("Select Midfielder", sorted(midfielder_list))
            plot_midfielder_report_card(events, selected_midfielder, full_midfielder_events=full_comp_events)

    elif viz_option == "Forward Report Card":
        st.header("Forward Report Card")
        # Define forward positions for filtering.
        forward_positions = ["Center Forward", "Left Center Forward", "Right Center Forward"]
        forwards_subset = events[events.position.isin(forward_positions)]
        forward_list = forwards_subset.player.dropna().unique().tolist()
        if not forward_list:
            st.error("No forward data available in the selected match(es).")
        else:
            selected_forward = st.sidebar.selectbox("Select Forward", sorted(forward_list))
            plot_forward_report_card(events, selected_forward, full_forward_events=full_comp_events)

    elif viz_option == "Team Passing Network":
        st.header("Team Passing Network")
        plot_team_passing_network(events, team)

    elif viz_option == "Team xG Hot Zones":
        st.header("Team xG Hot Zones")
        plot_team_xg_heatmap(events, team)
    
    elif viz_option == "xG vs. Actual Goals":
        st.header("xG vs. Actual Goals")
        plot_team_xg_vs_actual_goals(events, team, matches)


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
    ax.set_title(f'{player_name} Progressions into Final 3rd', fontsize=30, color='black')
    
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
        marker='football',  # 'football' marker works if mplsoccer version supports it
        label='Goal',
        ax=ax
    )

    # Add a legend and a title
    ax.legend(facecolor='white', handlelength=5, edgecolor='None', fontsize=20, loc='best')
    ax.set_title(f"{player_name} Shot Map", fontsize=20)
    st.pyplot(fig)

def plot_goalkeeper_report_card(events, goalkeeper_name, full_goalkeeper_events):
    """
    Displays a Goalkeeper Report Card for the selected goalkeeper.
    
    For each of the following metrics:
      - Goal Keeper (saves / key interventions)
      - Pass
      - Ball Receipt*
      - Pressure
      - Clearance
      - Block
      - Shield
      
    This function computes:
      1. The raw count of events for the selected goalkeeper (from tournament-wide data).
      2. The tournament-wide percentile ranking of that count among all goalkeepers.
      
    Only events from players with position "Goalkeeper" (in the full tournament data) are compared.
    """
    # Recommended metrics for goalkeepers
    metrics = [
        "Goal Keeper",
        "Pass",
        "Ball Receipt*",
        "Pressure",
        "Clearance",
        "Block",
        "Shield"
    ]
    
    # Filter the full competition events to include only goalkeepers.
    full_gks = full_goalkeeper_events[full_goalkeeper_events.position == "Goalkeeper"]
    
    # For tournament-wide comparisons, get the selected goalkeeper's events from full data.
    selected_gk_events = full_goalkeeper_events[full_goalkeeper_events.player == goalkeeper_name]
    
    report_rows = []
    for metric in metrics:
        # Count the number of events of this type for the selected goalkeeper.
        selected_count = selected_gk_events[selected_gk_events['type'] == metric].shape[0]
        
        # Group the full goalkeeper data by player for this event.
        gk_counts_df = full_gks[full_gks['type'] == metric].groupby('player').size().reset_index(name='count')
        
        if gk_counts_df.empty:
            perc = 0
        else:
            perc = percentileofscore(gk_counts_df['count'], selected_count, kind='mean')
        
        report_rows.append({
            "Metric": metric,
            "Count": selected_count,
            "Percentile": f"{perc:.1f}%"
        })
    
    df_report = pd.DataFrame(report_rows)
    
    st.markdown(f"### Goalkeeper Report Card: {goalkeeper_name}")
    st.markdown("#### Event Metrics with Tournament-wide Percentiles (Goalkeepers Only)")
    st.dataframe(df_report)
    
    st.markdown("#### Passing Map")
    # Filter for passes made by the goalkeeper.
    gk_passes = selected_gk_events[selected_gk_events.type == "Pass"]
    
    if gk_passes.empty:
        st.info("No passing data available for this goalkeeper in the selected match(es).")
    else:
        # Draw a full pitch.
        pitch = Pitch(pitch_type='statsbomb', pitch_color='white', line_color='black', line_zorder=2)
        fig, ax = pitch.draw(figsize=(12, 8))
        
        # For each pass, plot an arrow from the starting point to the pass end.
        for _, row in gk_passes.iterrows():
            if pd.notna(row['pass_end_x']) and pd.notna(row['pass_end_y']):
                pitch.arrows(
                    row['x'], row['y'],
                    row['pass_end_x'], row['pass_end_y'],
                    width=2, headwidth=8, headlength=5,
                    color="orange",
                    ax=ax, zorder=2
                )
        ax.set_title(f"{goalkeeper_name} Passing Map", fontsize=20)
        st.pyplot(fig)

def plot_defender_report_card(events, defender_name, full_defender_events):
    """
    Displays a Defender Report Card for the selected defender.
    
    It computes, for each of the recommended defensive metrics:
      - Clearance
      - Block
      - Interception
      - Duel
      - Ball Recovery
      - Pressure
      - 50/50
      - Dribbled Past
      - Miscontrol
      - Dispossessed
      - Foul Committed
      - Foul Won
      
    the raw count and the tournament-wide percentile (comparing only defenders) of that count.
    
    Only events from defender positions are considered. The recommended defender positions are:
      "Center Back", "Left Center Back", "Right Center Back", "Left Wing Back", "Right Wing Back"
    """
    # Recommended metrics for defenders.
    recommended_defender_metrics = [
        "Clearance",
        "Block",
        "Interception",
        "Duel",
        "Ball Recovery",
        "Pressure",
        "50/50",
        "Dribbled Past",
        "Miscontrol",
        "Dispossessed",
        "Foul Committed",
        "Foul Won"
    ]
    
    # Define typical defender positions.
    defender_positions = [
        "Center Back",
        "Left Center Back",
        "Right Center Back",
        "Left Wing Back",
        "Right Wing Back"
    ]
    
    # Filter the full tournament events to include only defenders.
    full_defenders = full_defender_events[full_defender_events.position.isin(defender_positions)]
    
    # Use the full tournament data for the selected defender.
    selected_defender_events = full_defender_events[full_defender_events.player == defender_name]
    
    # Build report rows for each recommended metric.
    report_rows = []
    for metric in recommended_defender_metrics:
        # Get the selected defender's count for this metric.
        selected_count = selected_defender_events[selected_defender_events['type'] == metric].shape[0]
        
        # For tournament-wide percentiles, group full defenders by player for this metric.
        defender_counts_df = full_defenders[full_defenders['type'] == metric] \
            .groupby('player').size().reset_index(name='count')
        
        if defender_counts_df.empty:
            perc = 0
        else:
            # Compute the percentile ranking (using kind='mean' for consistency).
            perc = percentileofscore(defender_counts_df['count'], selected_count, kind='mean')
        
        report_rows.append({
            "Metric": metric,
            "Count": selected_count,
            "Percentile": f"{perc:.1f}%"
        })
    
    # Create a DataFrame for display.
    df_report = pd.DataFrame(report_rows)
    
    st.markdown(f"### Defender Report Card: {defender_name}")
    st.markdown("#### Defensive Event Metrics with Tournament-wide Percentiles (Defenders Only)")
    st.dataframe(df_report)

def plot_midfielder_report_card(events, midfielder_name, full_midfielder_events):
    """
    Displays a Midfielder Report Card for the selected midfielder.
    
    For each of the following event types:
       - Pass
       - Ball Receipt*
       - Carry
       - Dribble
       - Shot
       - Interception
       - Duel
       - Foul Won
       - Pressure
       - Dispossessed
       - Miscontrol
       - Dribbled Past
       - Ball Recovery
       - Shield
       
    This function computes:
       1. The raw count of events for the selected midfielder (using tournament-wide data)
       2. The tournament-wide percentile ranking of that count among all midfielders.
       
    Only midfielders (as defined by the list of positions below) are compared.
    """
    # Midfielder positions:
    midfielder_positions = [
        "Center Attacking Midfield",
        "Center Defensive Midfield",
        "Left Attacking Midfield",
        "Left Center Midfield",
        "Left Defensive Midfield",
        "Left Midfield",
        "Right Attacking Midfield",
        "Right Center Midfield",
        "Right Defensive Midfield",
        "Right Midfield",
        "Left Wing",
        "Right Wing"
    ]
    
    # Filter the full tournament events to include only midfielders.
    full_midfielders = full_midfielder_events[full_midfielder_events.position.isin(midfielder_positions)]
    
    # For tournament-wide comparisons, use the full tournament data.
    # Get the selected midfielder's events from the full dataset.
    selected_midfielder_events = full_midfielder_events[full_midfielder_events.player == midfielder_name]
    
    # Define the event list for midfielders:
    event_list = [
        "Pass",
        "Ball Receipt*",
        "Carry",
        "Dribble",
        "Shot",
        "Interception",
        "Duel",
        "Foul Won",
        "Pressure",
        "Dispossessed",
        "Miscontrol",
        "Dribbled Past",
        "Ball Recovery",
        "Shield"
    ]
    
    report_rows = []
    for ev in event_list:
        # Count the number of events of type `ev` for the selected midfielder.
        selected_count = selected_midfielder_events[selected_midfielder_events['type'] == ev].shape[0]
        
        # For tournament-wide percentiles, group the full midfielder data by player for this event.
        midfielder_counts_df = full_midfielders[full_midfielders['type'] == ev] \
            .groupby('player').size().reset_index(name='count')
        
        if midfielder_counts_df.empty:
            perc = 0
        else:
            # Compute the percentile ranking of the selected count among all midfielders.
            perc = percentileofscore(midfielder_counts_df['count'], selected_count, kind='mean')
        
        report_rows.append({
            "Event": ev,
            "Count": selected_count,
            "Percentile": f"{perc:.1f}%"
        })
    
    df_report = pd.DataFrame(report_rows)
    
    st.markdown(f"### Midfielder Report Card: {midfielder_name}")
    st.markdown("#### Event Metrics with Tournament-wide Percentiles (Midfielders Only)")
    st.dataframe(df_report)

def plot_forward_report_card(events, forward_name, full_forward_events):
    """
    Displays a Forward Report Card for the selected forward.
    
    For each of the following metrics:
      - Shot (all shot events)
      - Goal (derived: shot events with shot_outcome == "Goal")
      - Pass
      - Ball Receipt*
      - Dribble
      - Duel
      - Offside
      - Foul Won
      - Pressure
      - Miscontrol
      
    the function computes:
      1. The raw count for the selected forward (from tournament-wide data).
      2. The tournament-wide percentile ranking of that count among all forwards.
    
    Only forwards (defined as those whose position is one of:
      "Center Forward", "Left Center Forward", "Right Center Forward")
    are included in the comparison.
    """
    # Recommended forward metrics
    metrics = [
        "Shot",
        "Goal",
        "Pass",
        "Ball Receipt*",
        "Dribble",
        "Duel",
        "Offside",
        "Foul Won",
        "Pressure",
        "Miscontrol"
    ]
    
    # Define typical forward positions.
    forward_positions = ["Center Forward", "Left Center Forward", "Right Center Forward"]
    
    # Filter the full tournament events to include only forwards.
    full_forwards = full_forward_events[full_forward_events.position.isin(forward_positions)]
    
    # For tournament-wide comparisons, get the selected forward's events from the full data.
    selected_forward_events = full_forward_events[full_forward_events.player == forward_name]
    
    report_rows = []
    for metric in metrics:
        if metric == "Goal":
            # For "Goal", count shot events where shot_outcome is "Goal".
            selected_count = selected_forward_events[
                (selected_forward_events.type == "Shot") &
                (selected_forward_events.shot_outcome == "Goal")
            ].shape[0]
            forward_counts_df = full_forwards[
                (full_forwards.type == "Shot") &
                (full_forwards.shot_outcome == "Goal")
            ].groupby('player').size().reset_index(name='count')
        else:
            selected_count = selected_forward_events[selected_forward_events['type'] == metric].shape[0]
            forward_counts_df = full_forwards[full_forwards['type'] == metric] \
                .groupby('player').size().reset_index(name='count')
        
        if forward_counts_df.empty:
            perc = 0
        else:
            perc = percentileofscore(forward_counts_df['count'], selected_count, kind='mean')
        
        report_rows.append({
            "Metric": metric,
            "Count": selected_count,
            "Percentile": f"{perc:.1f}%"
        })
    
    df_report = pd.DataFrame(report_rows)
    
    st.markdown(f"### Forward Report Card: {forward_name}")
    st.markdown("#### Event Metrics with Tournament-wide Percentiles (Forwards Only)")
    st.dataframe(df_report)

def plot_team_passing_network(events, team):
    """
    Plots a passing network for the selected team using only the starting eleven.
    
    Steps:
      1. Filter the events for the selected team and only successful passes.
      2. Determine the starting eleven as the top 11 players (by overall pass involvement).
      3. Filter passes so that both the passer and the recipient are in the starting eleven.
      4. Compute an average (x,y) position for each player (node) based on their passing (as a passer and as a receiver).
      5. Draw a pitch, then for each passing pair draw an arrow whose thickness is proportional to the pass count.
      6. Draw nodes with sizes proportional to each player’s total pass involvement.
    """
    # Filter events for the selected team and only successful passes (pass_outcome is NaN for completed passes)
    team_passes = events[
        (events.team == team) &
        (events.type == "Pass") &
        (events.pass_outcome.isna())
    ].copy()
    
    # Determine all players involved (as passer or recipient)
    players_series = pd.concat([team_passes["player"], team_passes["pass_recipient"]])
    players_counts = players_series.value_counts()  # total involvement count per player
    
    # Determine the starting eleven: take top 11 by involvement
    starting_eleven = players_counts.head(11).index.tolist()
    
    # Filter team_passes to only include events where both passer and recipient are in starting eleven.
    team_passes = team_passes[
        team_passes["player"].isin(starting_eleven) &
        team_passes["pass_recipient"].isin(starting_eleven)
    ]
    
    # Group passes by passer and recipient and compute average positions and pass counts.
    pass_group = team_passes.groupby(["player", "pass_recipient"]).agg({
        "x": "mean",
        "y": "mean",
        "pass_end_x": "mean",
        "pass_end_y": "mean"
    }).reset_index()
    # Add a column with the pass count between each pair.
    pass_group["pass_count"] = team_passes.groupby(["player", "pass_recipient"]).size().values
    
    # Compute nodes: For each player in the starting eleven, compute their average (x,y) position.
    nodes = []
    for player in starting_eleven:
        # Get starting locations (when the player makes a pass)
        passer_locs = team_passes[team_passes["player"] == player][["x", "y"]]
        # Get receiving locations (when the player is the recipient)
        receiver_locs = team_passes[team_passes["pass_recipient"] == player][["pass_end_x", "pass_end_y"]]
        if not passer_locs.empty and not receiver_locs.empty:
            avg_x = np.mean(np.concatenate([passer_locs["x"].values, receiver_locs["pass_end_x"].values]))
            avg_y = np.mean(np.concatenate([passer_locs["y"].values, receiver_locs["pass_end_y"].values]))
        elif not passer_locs.empty:
            avg_x = passer_locs["x"].mean()
            avg_y = passer_locs["y"].mean()
        elif not receiver_locs.empty:
            avg_x = receiver_locs["pass_end_x"].mean()
            avg_y = receiver_locs["pass_end_y"].mean()
        else:
            avg_x, avg_y = 0, 0
        nodes.append({
            "player": player,
            "x": avg_x,
            "y": avg_y,
            "total_passes": players_counts[player]  # overall involvement for scaling marker size
        })
    nodes = pd.DataFrame(nodes)
    
    # Create a pitch using mplsoccer.
    pitch = Pitch(pitch_type="statsbomb", line_zorder=2, linewidth=2)
    fig, ax = pitch.draw(figsize=(12, 8))
    
    # Draw edges: for each passing pair, draw an arrow from the passer's node to the recipient's node.
    for idx, row in pass_group.iterrows():
        try:
            passer = nodes[nodes.player == row["player"]].iloc[0]
            recipient = nodes[nodes.player == row["pass_recipient"]].iloc[0]
        except IndexError:
            continue
        # Draw an arrow with width proportional to pass_count.
        ax.arrow(passer.x, passer.y,
                recipient.x - passer.x, recipient.y - passer.y,
                width=row["pass_count"] * 0.05,  # reduced scaling factor for thinner lines
                color="blue", alpha=0.7,
                head_width=4, head_length=4, zorder=1)
    
    # Draw nodes: Plot each player's node as a red circle.
    for idx, row in nodes.iterrows():
        # Set marker size proportional to total pass involvement.
        node_size = row["total_passes"] * 2  # adjust scaling factor as needed
        ax.scatter(row.x, row.y, s=node_size, color="red", zorder=3)
        # Label the node with the player's name.
        ax.text(row.x, row.y, row.player, fontsize=10, ha="center", va="center", zorder=4)
    
    ax.set_title(f"Team Passing Network for {team} (Starting Eleven)", fontsize=20)
    st.pyplot(fig)

def plot_team_xg_heatmap(events, team):

    """
    Plots a heatmap showing the total xG (expected goals) accumulated in different zones
    on the pitch for a selected team.
    
    This uses the 'shot_statsbomb_xg' metric, aggregated over shot end locations.
    """
    # Filter events for the selected team and for shot events.
    team_shots = events[(events.team == team) & (events.type == "Shot")].copy()
    if team_shots.empty:
        st.error("No shot data available for the selected team.")
        return
    
    # Ensure shot end coordinates are available.
    # If not already extracted, try to extract them from 'shot_end_location'.
    if "shot_end_x" not in team_shots.columns or "shot_end_y" not in team_shots.columns:
        team_shots[['shot_end_x', 'shot_end_y']] = team_shots['shot_end_location'].apply(
            lambda loc: pd.Series(loc) if isinstance(loc, list) and len(loc) == 2 else pd.Series([None, None])
        )
    
    # Drop rows with missing coordinates.
    team_shots = team_shots.dropna(subset=["shot_end_x", "shot_end_y"])
    
    # Create a pitch using mplsoccer.
    pitch = Pitch(pitch_type="statsbomb", line_zorder=2, linewidth=2)
    fig, ax = pitch.draw(figsize=(12, 8))
    
    # Create a hexbin plot:
    # - 'C' is set to the shot_statsbomb_xg values and we'll sum them in each bin.
    # - 'gridsize' controls the number of bins.
    hb = ax.hexbin(
        team_shots["shot_end_x"],
        team_shots["shot_end_y"],
        C=team_shots["shot_statsbomb_xg"],
        reduce_C_function=np.sum,
        gridsize=20,
        cmap="Reds",
        mincnt=1,
        edgecolors='grey'
    )
    
    # Add a colorbar to show the scale (total xG per bin).
    fig.colorbar(hb, ax=ax, label="Total xG")
    ax.set_title(f"{team} xG Hot Zones", fontsize=20)
    
    st.pyplot(fig)

def plot_team_xg_vs_actual_goals(events, team, matches):
    """
    Plots a scatter plot comparing expected goals (xG) and actual goals for the selected team.
    
    For each match, the function computes:
      - Total xG: Sum of "shot_statsbomb_xg" over all shot events.
      - Actual Goals: Count of shot events where shot_outcome == "Goal".
    
    The function then merges this summary with the matches DataFrame to create a "game_name" 
    (for example, "2024-06-15 - Home vs Away") used in hover data instead of the raw match_id.
    
    A diagonal line (x = y) is added as a reference.
    """
    # Filter shot events for the selected team.
    team_shots = events[(events.team == team) & (events.type == "Shot")].copy()
    if team_shots.empty:
        st.error("No shot data available for the selected team.")
        return
    
    # Group by match_id and compute total xG and actual goals.
    summary = team_shots.groupby("match_id").apply(
        lambda df: pd.Series({
            "total_xG": df["shot_statsbomb_xg"].sum(),
            "actual_goals": df[df["shot_outcome"] == "Goal"].shape[0]
        })
    ).reset_index()
    
    # Merge with matches DataFrame to get additional match details.
    # Assume matches DataFrame contains columns: match_id, home_team, away_team, match_date.
    summary = summary.merge(matches[['match_id', 'home_team', 'away_team', 'match_date']],
                              on='match_id', how='left')
    
    # Create a "game_name" column (adjust formatting as needed)
    summary["game_name"] = summary["match_date"].astype(str) + " - " + summary["home_team"] + " vs " + summary["away_team"]
    
    # Create a scatter plot using Plotly Express, with hover_data showing game_name.
    fig = px.scatter(
        summary, 
        x="total_xG", 
        y="actual_goals",
        hover_data=["game_name"],
        labels={"total_xG": "Total xG", "actual_goals": "Actual Goals"},
        title=f"{team} xG vs. Actual Goals by Match"
    )
    
    # Determine an axis limit for the diagonal line.
    max_val = max(summary["total_xG"].max(), summary["actual_goals"].max()) * 1.1
    fig.add_shape(
        type="line",
        x0=0, y0=0,
        x1=max_val, y1=max_val,
        line=dict(color="grey", dash="dash")
    )
    
    st.plotly_chart(fig, use_container_width=True)

if __name__ == "__main__":
    main()