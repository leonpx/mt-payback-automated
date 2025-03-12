#!/usr/bin/env python

from flask import (
    Flask,
    render_template,
    request,
    make_response,
    send_from_directory,
    jsonify,
)
import datetime
from dateutil import parser
import pytz
import requests
import operators

app = Flask(__name__)

tz = pytz.timezone("Europe/Stockholm")

@app.route("/", methods=["GET"])
def index():
    resp = make_response(
        render_template(
            "main.html",
            today=datetime.date.today(),
            **request.cookies,
        )
    )

    if (
        request.cookies.get("expirydate") == None
        or datetime.datetime.strptime(
            request.cookies.get("expirydate"), "%Y-%m-%d"
        ).date()
        < datetime.date.today()
    ):
        resp.delete_cookie("expirydate")
        resp.delete_cookie("ticketholder")
        resp.delete_cookie("ticket")

    return resp


@app.route("/static/<path:path>")
def send_static_file(path):
    return send_from_directory("static", path)


@app.route("/api/submit", methods=["POST"])
def submit():
    operator = request.json.get("operator")
    if operator == "sj":
        op = operators.SJ()
    elif operator == "mt":
        op = operators.MT()

    r = op.submit(
        request.json.get("ticket"),
        request.json.get("from"),
        request.json.get("to"),
        request.json.get("departureDate"),
        request.json.get("departureTime"),
        request.json.get("customer"),
    )

    if r:
        resp = make_response("Request submitted!")

        return resp
    else:
        return f"Something went wrong submitting the request: {r.text}", 500


@app.route(
    "/api/departures/<departure_station>/<arrival_station>/<date>", methods=["GET"]
)
def get_departures(departure_station, arrival_station, date):
    r = requests.get(
        "https://evf-regionsormland.preciocloudapp.net/api/TrainStations/GetDepartureTimeList",
        params={
            "departureStationId": departure_station,
            "arrivalStationId": arrival_station,
            "departureDate": date,
        },
    )

    return jsonify(sorted(r.json()["data"]))

@app.route("/api/submit_selected", methods=["POST"])
def submit_selected():
    data = request.get_json()
    items = data.get("items", [])
    if not items:
        return jsonify({"status": "error", "message": "No items provided"}), 400

    op = operators.MT()  # Using the MT class as in your submit() route
    submitted_count = 0
    errors = []

    for item in items:
        try:
            # Call op.submit() for each selected item.
            # It is assumed that each item contains the necessary keys.
            r = op.submit(
                item.get("ticket"),
                item.get("from"),
                item.get("to"),
                item.get("departureDate"),
                item.get("departureTime"),
                data.get("customer")  # Pass along customer info if available
            )
            #r = True
            if r:
                submitted_count += 1
            else:
                errors.append(f"Submission failed for train {item.get('ticket')}")
        except Exception as e:
            errors.append(str(e))

    if errors:
        return jsonify({
            "status": "error",
            "message": "Some errors occurred while submitting selected items.",
            "errors": errors
        }), 500

    return jsonify({
        "status": "success",
        "submitted": submitted_count,
        "message": f"{submitted_count} applications submitted."
    })

@app.route("/api/auto_submit", methods=["POST"])
def auto_submit():
    # Read inputs from JSON payload.
    tv_api_key = request.json.get("tv_api_key", "").strip()
    if not tv_api_key:
        return "Trafikverket API key not provided", 400

    start_time_input = request.json.get("startTime", "").strip()  # expected "hh:mm"
    auto_date_input = request.json.get("date", "").strip()         # expected "YYYY-MM-DD"
    
    now = datetime.datetime.now(tz)
    
    try:
        # Determine base date.
        if auto_date_input:
            base_date = datetime.datetime.strptime(auto_date_input, "%Y-%m-%d").date()
        else:
            base_date = now.date()
            
        if start_time_input:
            # Use provided start time with the base date.
            user_time = datetime.datetime.strptime(start_time_input, "%H:%M").time()
            start_time = datetime.datetime.combine(base_date, user_time)
            start_time = tz.localize(start_time)
            end_time = start_time + datetime.timedelta(hours=24)
        else:
            if auto_date_input:
                # If a date was provided but no start time, use the entire day.
                start_time = tz.localize(datetime.datetime.combine(base_date, datetime.time.min))
                end_time = tz.localize(datetime.datetime.combine(base_date, datetime.time.max))
            else:
                # Otherwise, use the previous 24 hours (ending now).
                end_time = now
                start_time = now - datetime.timedelta(hours=24)
    except Exception as e:
        return f"Invalid time or date format: {str(e)}", 400

    # Get departures using the Trafikverket API.
    try:
        all_departures = get_delayed_or_cancelled("U", "Cst", start_time, end_time, tv_api_key)
    except Exception as e:
        print(e)
        return f"Error retrieving departures: {str(e)}", 500

    # Here you can optionally filter departures further based on the time window,
    # if needed. In this example, we assume get_delayed_or_cancelled() has already done that.
    filtered = all_departures

    # Build a list of submission items.
    submission_items = []
    for dep in filtered:
        try:
            dt = parser.parse(dep["departureTime"])
            # Format the departure time as "hh:mm dd-mm-yy"
            formatted_time = dt.strftime("%H:%M %d-%m-%y")
            if dep.get("canceled"):
                item = {
                    "ticket": dep.get("ticket"),
                    "from": dep.get("from"),
                    "to": dep.get("to"),
                    "departureDate": dep.get("departureDate"),
                    "departureTime": dep.get("departureTime"),
                    "status": "cancelled"
                }
            else:
                item = {
                    "ticket": dep.get("ticket"),
                    "from": dep.get("from"),
                    "to": dep.get("to"),
                    "departureDate": dep.get("departureDate"),
                    "departureTime": dep.get("departureTime"),
                    "status": f"delayed {dep.get('delay'):.0f} min"
                }
            submission_items.append(item)
        except Exception as e:
            print(e)
            continue

    if not submission_items:
        result = f"No delays or cancellations found between {start_time.strftime('%H:%M %d-%m-%y')} and {end_time.strftime('%H:%M %d-%m-%y')}."
        return jsonify({"status": "success", "found": 0, "items": [], "message": result})

    # Instead of submitting automatically here, we return the list so the user can select.
    result = (
        f"{len(submission_items)} delays or cancellations found between "
        f"{start_time.strftime('%H:%M %d-%m-%y')} and {end_time.strftime('%H:%M %d-%m-%y')}."
    )
    return jsonify({"status": "success", "found": len(submission_items), "items": submission_items, "message": result})


def get_delayed_or_cancelled(departure_station, arrival_station, start_time, end_time, tv_api_key):
    """
    Uses Trafikverket API to retrieve TrainAnnouncement data for the entire day
    (from 00:00 to 24:00) for the given departure_station and arrival_station.
    
    Returns a list of dictionaries for announcements that were either cancelled
    or delayed by more than 20 minutes. Each dictionary contains:
      - ticket: the train identifier (AdvertisedTrainIdent)
      - from: departure station (from the announcement's FromLocation if available,
              otherwise the provided departure_station)
      - to: arrival station (from the announcement's ToLocation if available,
            otherwise the provided arrival_station)
      - departureDate: the date (YYYY-MM-DD)
      - departureTime: the advertised time (AdvertisedTimeAtLocation) from the announcement
      - canceled: boolean (True if cancelled)
      - delay: delay in minutes (if not cancelled), else None
      - ActivityType: the activity type (e.g., "Avgang" or "Ankomst")
    """

    # Add 1 hour to compensate for arrival time, ugly fix
    end_time = end_time + datetime.timedelta(hours=1)

    # Convert start and end times to ISO 8601 format.
    start_str = start_time.isoformat()
    end_str = end_time.isoformat()
    print(f"START: {start_str}, END: {end_str}")
    
    # Build the XML query for Trafikverket API, using the provided API key.
    query = f"""
        <REQUEST>
          <LOGIN authenticationkey="{tv_api_key}" />
          <QUERY objecttype="TrainAnnouncement" schemaversion="1.9" limit="1000">
            <FILTER>
              <GT name="AdvertisedTimeAtLocation" value="{start_str}" />
              <LT name="AdvertisedTimeAtLocation" value="{end_str}" />
              <EQ name="Operator" value="TDEV" />
              <OR>
                <EQ name="LocationSignature" value="{departure_station}" />
                <EQ name="LocationSignature" value="{arrival_station}" />
              </OR>
            </FILTER>
            <INCLUDE>AdvertisedTrainIdent</INCLUDE>
            <INCLUDE>AdvertisedTimeAtLocation</INCLUDE>
            <INCLUDE>TimeAtLocation</INCLUDE>
            <INCLUDE>LocationSignature</INCLUDE>
            <INCLUDE>Operator</INCLUDE>
            <INCLUDE>Canceled</INCLUDE>
            <INCLUDE>ActivityType</INCLUDE>
          </QUERY>
        </REQUEST>
    """
    tv_url = "https://api.trafikinfo.trafikverket.se/v2/data.json"
    headers = {"Content-Type": "text/xml"}
    response = requests.post(tv_url, data=query.encode("utf-8"), headers=headers)
    response.raise_for_status()
    tv_data = response.json()
    
    trains = {}

    for result in tv_data.get("RESPONSE", {}).get("RESULT", []):
        for ann in result.get("TrainAnnouncement", []):
            train_id = ann.get("AdvertisedTrainIdent", "N/A")
            loc = ann.get("LocationSignature", None)
            # Only consider announcements for U or Cst.
            if loc not in {departure_station, arrival_station}:
                continue
            try:
                adv_time = parser.parse(ann.get("AdvertisedTimeAtLocation"))
            except Exception:
                continue
            trains.setdefault(train_id, []).append({
                "location": loc,
                "adv_time": adv_time,
                "adv_time_str": ann.get("AdvertisedTimeAtLocation"),
                "time_at_location_str": ann.get("TimeAtLocation"),
                "canceled": ann.get("Canceled", False),
                "ActivityType": ann.get("ActivityType")
            })

    delayed_or_cancelled = []

    for train_id, anns in trains.items():
        # Build lists filtered by station and ActivityType.
        u_departures = [a for a in anns if a["location"] == departure_station and a.get("ActivityType") == "Avgang"]
        u_arrivals   = [a for a in anns if a["location"] == departure_station and a.get("ActivityType") == "Ankomst"]
        cst_departures = [a for a in anns if a["location"] == arrival_station and a.get("ActivityType") == "Avgang"]
        cst_arrivals   = [a for a in anns if a["location"] == arrival_station and a.get("ActivityType") == "Ankomst"]
    
        candidate = None
        # Option 1: Journey from U to Cst:
        if u_departures and cst_arrivals:
            dep_ann = min(u_departures, key=lambda a: a["adv_time"])
            arr_ann = max(cst_arrivals, key=lambda a: a["adv_time"])
            if dep_ann["adv_time"] < arr_ann["adv_time"]:
                candidate = (departure_station, dep_ann, arrival_station, arr_ann)
        # Option 2: Journey from Cst to U:
        if candidate is None and cst_departures and u_arrivals:
            dep_ann = min(cst_departures, key=lambda a: a["adv_time"])
            arr_ann = max(u_arrivals, key=lambda a: a["adv_time"])
            if dep_ann["adv_time"] < arr_ann["adv_time"]:
                candidate = (arrival_station, dep_ann, departure_station, arr_ann)
        
        if candidate is None:
            continue
    
        dep_station, dep_ann, arr_station, arr_ann = candidate
    
        if arr_ann["canceled"]:
            status = "canceled"
            delay = None
        else:
            try:
                adv_arr = parser.parse(arr_ann["adv_time_str"])
                actual_arr = parser.parse(arr_ann["time_at_location_str"])
                delay = (actual_arr - adv_arr).total_seconds() / 60
            except Exception:
                delay = None
            status = "delay" if delay is not None and delay > 20 else "ok"
    
        if status in {"canceled", "delay"}:
            date_str = dep_ann["adv_time"].strftime("%Y-%m-%d")
            time_str = dep_ann["adv_time"].strftime("%H:%M:%S")
            print(f"DATE: {date_str}, TIME: {time_str}")
            delayed_or_cancelled.append({
                "ticket": train_id,
                "from": dep_station,
                "to": arr_station,
                "departureDate": date_str,
                "departureTime": time_str,
                "canceled": arr_ann["canceled"],
                "delay": delay,
                "ActivityType": arr_ann["ActivityType"]
            })

    return delayed_or_cancelled

def get_train_number(departure_station, arrival_station, departure_time):
    r = requests.get(
        "https://evf-regionsormland.preciocloudapp.net/api/TrainStations/GetDistance",
        params={
            "departureStationId": departure_station,
            "arrivalStationId": arrival_station,
            "departureDate": departure_time,
        },
    )

    return r.json()["data"]["trafikverketTrainId"]


@app.route("/api/arrival_stations/<station>", methods=["GET"])
def get_arrival_stations(station):
    arrival_stations = {
        "U": ["Cst", "Srv", "Kn", "Mr", "Fvk", "Gä"],
        "Kn": ["U", "Cst", "Mr"],
        "Mr": ["U", "Cst", "Kn"],
        "Cst": ["U", "Kn", "Mr"],
        "Srv": ["U", "Fvk", "Gä"],
    }

    station_names = {
        "U": "Uppsala C",
        "Cst": "Stockholm C",
        "Srv": "Storvreta",
        "Fvk": "Furuvik",
        "Gä": "Gävle",
        "Kn": "Knivsta",
        "Mr": "Märsta",
    }

    return {
        "stations": [
            {"name": x, "longname": station_names[x]} for x in arrival_stations[station]
        ]
    }


def main():
    app.run(debug=True)


if __name__ == "__main__":
    main()
