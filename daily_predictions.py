from features.predictions.predictions import (
    join_current_market,
    join_current_squad,
    live_data_predictions,
)
from features.predictions.preprocessing import preprocess_player_data, split_data
from features.predictions.modeling import evaluate_model, train_model
from features.predictions.data_handler import (
    check_if_data_reload_needed,
    create_player_data_table,
    load_player_data_from_db,
    save_player_data_to_db,
)
from features.budgets import calc_manager_budgets

import pandas as pd


last_mv_values = 365
last_pfm_values = 50
competition_ids = [1]
start_budget = 50_000_000
league_start_date = "2025-08-08"

features = [
    "p",
    "mv",
    "days_to_next",
    "mv_change_1d",
    "mv_trend_1d",
    "mv_change_3d",
    "mv_vol_3d",
    "mv_trend_7d",
    "market_divergence",
]
target = "mv_target_clipped"

pd.options.display.float_format = lambda value: "{:,.0f}".format(value).replace(",", ".")
pd.set_option("display.max_columns", None)
pd.set_option("display.max_rows", None)
pd.set_option("display.width", 1000)


def run_analysis(token, league_id):
    """Run predictions for a league and return all tables and model metrics."""
    manager_budgets_df = calc_manager_budgets(
        token, league_id, league_start_date, start_budget
    )

    create_player_data_table()
    reload_data = check_if_data_reload_needed()
    save_player_data_to_db(
        token, competition_ids, last_mv_values, last_pfm_values, reload_data
    )
    player_df = load_player_data_from_db()

    proc_player_df, today_df = preprocess_player_data(player_df)
    X_train, X_test, y_train, y_test = split_data(proc_player_df, features, target)

    model = train_model(X_train, y_train)
    signs_percent, rmse, mae, r2 = evaluate_model(model, X_test, y_test)

    live_predictions_df = live_data_predictions(today_df, model, features)
    market_recommendations_df = join_current_market(
        token, league_id, live_predictions_df
    )
    squad_recommendations_df = join_current_squad(
        token, league_id, live_predictions_df
    )

    return {
        "manager_budgets": manager_budgets_df,
        "market_recommendations": market_recommendations_df,
        "squad_recommendations": squad_recommendations_df,
        "metrics": {
            "Signs correct": signs_percent,
            "RMSE": rmse,
            "MAE": mae,
            "R2": r2,
        },
    }


def export_recommendations(results, alias):
    """Write the recommendation tables to the legacy Excel output."""
    filename = f"recommendations_{alias}.xlsx"
    with pd.ExcelWriter(filename, engine="openpyxl") as writer:
        results["market_recommendations"].to_excel(
            writer, sheet_name="Market Recommendations", index=False
        )
        results["squad_recommendations"].to_excel(
            writer, sheet_name="Squad Recommendations", index=False
        )
    return filename


if __name__ == "__main__":
    import os
    import sys

    from dotenv import load_dotenv
    from kickbase_api.league import get_league_id
    from kickbase_api.user import login

    load_dotenv()

    league_options = {
        "h": "CROFL (Chicken River Official Football League)",
        "m": "Ok Garmin, Liga speichern",
    }
    if len(sys.argv) != 2 or sys.argv[1] not in league_options:
        raise ValueError("Usage: python daily_predictions.py [h|m]")

    username = os.getenv("KICK_USER")
    password = os.getenv("KICK_PASS")
    if not username or not password:
        raise ValueError("KICK_USER and KICK_PASS must be set")

    token = login(username, password)
    league_id = get_league_id(token, league_options[sys.argv[1]])
    results = run_analysis(token, league_id)
    output_file = export_recommendations(results, sys.argv[1])

    print("\n=== Manager Budgets ===")
    print(results["manager_budgets"])
    print("\n=== Market Recommendations ===")
    print(results["market_recommendations"])
    print("\n=== Squad Recommendations ===")
    print(results["squad_recommendations"])
    print(f"\nRecommendations written to {output_file}")
