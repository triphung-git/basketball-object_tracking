"""Versioned v2 annotation headers; templates contain no invented labels/players."""
SCHEMA_VERSION = "2.0.1"
ANNOTATION_HEADERS = {
    "shots": "shot_id,video_id,shooter_id,team_id,release_time_s,outcome_time_s,shot_type,result,score_time_s,notes",
    "rebounds": "rebound_id,video_id,shot_id,actor_id,team_id,rebound_time_s,rebound_type,notes",
    "passes": "pass_id,video_id,passer_id,receiver_id,team_id,release_time_s,receive_time_s,outcome",
    "assists": "assist_id,video_id,pass_id,shot_id,passer_id,scorer_id,team_id,assist_time_s,eligibility,notes",
    "coverage": "video_id,interval_id,start_time_s,end_time_s,status,notes",
    "reviews": "table_name,record_id,review_status,reviewer,reviewed_utc,review_notes",
    "player_positions": "position_id,video_id,player_id,team_id,time_s,x_image,y_image,x_court,y_court,visibility,notes",
    "identities": "identity_id,video_id,track_id,player_id,team_id,start_time_s,end_time_s,evidence,notes",
    "ball_control": "control_id,video_id,player_id,team_id,start_time_s,end_time_s,state,evidence_status,notes",
}
ID_COLUMNS = {table: header.split(",")[0] for table, header in ANNOTATION_HEADERS.items() if table != "reviews"}
ID_COLUMNS["coverage"] = "interval_id"
