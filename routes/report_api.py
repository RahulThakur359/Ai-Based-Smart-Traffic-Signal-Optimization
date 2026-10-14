import io
import csv
import datetime
from flask import Blueprint, jsonify, request, Response
from database.queries import get_analytics_summary, get_latest_traffic_records
from routes.traffic_api import traffic_state

report_api_bp = Blueprint('report_api', __name__, url_prefix='/api/reports')


@report_api_bp.route('/data', methods=['GET'])
@report_api_bp.route('/summary', methods=['GET'])
def get_reports_data():
    """
    Returns aggregated traffic analytics summary, per-road distributions,
    and recent execution records for the Performance Reports dashboard.
    """
    try:
        analytics = get_analytics_summary()
        return jsonify({
            'success': True,
            'summary': analytics,
            'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        })
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@report_api_bp.route('/export', methods=['GET', 'POST'])
def export_report():
    """
    Generates and downloads a structured CSV or JSON report containing
    traffic density, vehicle volume, congestion records, and signal optimization data.
    """
    report_type = request.args.get('type', 'daily').lower()
    export_format = request.args.get('format', 'csv').lower()

    road_labels = {
        'road1': 'Road 1 (North Branch)',
        'road2': 'Road 2 (East Branch)',
        'road3': 'Road 3 (South Branch)',
        'road4': 'Road 4 (West Branch)'
    }

    records = get_latest_traffic_records(limit=100)

    # Ensure current completed roads from live session are included
    existing_rids = {r.get('road_id') for r in records}
    for rid, st in traffic_state.items():
        if st.get('status') == 'COMPLETED' and rid not in existing_rids:
            records.append({
                'id': len(records) + 1,
                'road_id': rid,
                'vehicle_count': st.get('vehicle_count') or st.get('unique_vehicle_count') or 0,
                'density': round(float(st.get('density_percentage') or 0.0), 1),
                'congestion_level': st.get('congestion_level') or st.get('congestion') or 'NORMAL',
                'emergency_detected': False,
                'timestamp': datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            })

    if export_format == 'json':
        return jsonify({
            'success': True,
            'report_type': report_type,
            'generated_at': datetime.datetime.now().isoformat(),
            'total_records': len(records),
            'records': records
        })

    # Default CSV generation
    output = io.StringIO()
    writer = csv.writer(output)

    # Header section
    writer.writerow(["# AI-BASED TRAFFIC OPTIMIZATION SYSTEM - PERFORMANCE REPORT"])
    writer.writerow([f"# Report Type: {report_type.upper()} SUMMARY"])
    writer.writerow([f"# Generated At: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')}"])
    writer.writerow([])
    writer.writerow([
        "Record ID",
        "Timestamp",
        "Intersection Branch",
        "Vehicle Count",
        "Area Density (%)",
        "Congestion Level",
        "Emergency Detected"
    ])

    for idx, rec in enumerate(records, start=1):
        rid = rec.get('road_id', 'road1')
        branch_name = road_labels.get(rid, rid.upper())
        writer.writerow([
            rec.get('id', idx),
            rec.get('timestamp', datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")),
            branch_name,
            rec.get('vehicle_count', 0),
            f"{rec.get('density', 0.0)}%",
            rec.get('congestion_level', 'NORMAL'),
            "YES" if rec.get('emergency_detected') else "NO"
        ])

    csv_data = output.getvalue()
    filename = f"Traffic_{report_type.capitalize()}_Report_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    return Response(
        csv_data,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"}
    )


@report_api_bp.route('/generate', methods=['POST'])
def generate_report():
    """Compiles on-demand report analytics summary."""
    analytics = get_analytics_summary()
    return jsonify({
        'success': True,
        'message': 'Report compiled successfully.',
        'data': analytics
    })
