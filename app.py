from flask import Flask, render_template, request, jsonify, session
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from collections import defaultdict
import json

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///data.db'
app.secret_key = 'lol'
db = SQLAlchemy(app)

class UserData(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.String, unique=True, nullable=False)
    data = db.Column(db.String, nullable=False)

class Snapshot(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    month = db.Column(db.String(7), nullable=False)  # YYYY-MM
    average_data = db.Column(db.String, nullable=False)

    def to_dict(self):
        return {
            "id": self.id,
            "month": self.month,
            "average_data": eval(self.average_data)  # Assuming average_data is stored as a string representation of a dict
        }

def init_db():
    db.create_all()
    load_initial_data()

def load_initial_data():
    with open('september.json') as f:
        data = json.load(f)
    user_id = 'september_data'  # Assign a unique user_id for this data
    user_entry = UserData.query.filter_by(user_id=user_id).first()

    if user_entry:
        user_entry.data = str(data)
    else:
        new_entry = UserData(user_id=user_id, data=str(data))
        db.session.add(new_entry)
    db.session.commit()

@app.route('/')
def index():
    aggregated_data = compute_aggregated_data()
    averages = {key: sum(values) / len(values) for key, values in aggregated_data.items()}

    # Sort averages from high to low
    sorted_averages = dict(sorted(averages.items(), key=lambda item: item[1], reverse=True))

    # Get monthly snapshots from the database
    monthly_snapshots = Snapshot.query.order_by(Snapshot.month.desc()).all()

    # Convert Snapshot objects to dictionaries
    monthly_snapshots_dict = [snapshot.to_dict() for snapshot in monthly_snapshots]

    return render_template('index.html', averages=sorted_averages, snapshots=monthly_snapshots_dict)

@app.route('/add_data', methods=['POST'])
def add_data():
    data = request.json
    user_id = session.get('user_id', str(datetime.now().timestamp()))
    session['user_id'] = user_id

    user_entry = UserData.query.filter_by(user_id=user_id).first()

    if user_entry:
        user_entry.data = str(data)
    else:
        new_entry = UserData(user_id=user_id, data=str(data))
        db.session.add(new_entry)

    db.session.commit()
    return jsonify({"message": "Data added successfully"}), 200

@app.route('/take_snapshot', methods=['POST'])
def take_snapshot():
    try:
        aggregated_data = compute_aggregated_data()
        averages = {key: sum(values) / len(values) for key, values in aggregated_data.items()}

        month_str = datetime.now().strftime('%Y-%m')  # current month in YYYY-MM format
        snapshot_entry = Snapshot(month=month_str, average_data=str(averages))
        db.session.add(snapshot_entry)
        db.session.commit()

        response = {
            "message": "Snapshot taken successfully for month: " + month_str,
            "status": "success",
            "data": averages
        }
    except Exception as e:
        # Log the exception (optional)
        app.logger.error(f"Failed to take snapshot: {e}")

        response = {
            "message": "Failed to take snapshot",
            "status": "error",
            "error": str(e)
        }
        return jsonify(response), 500  # 500 Internal Server Error

    return jsonify(response), 200  # 200 OK

@app.route('/delete_snapshot/<int:snapshot_id>', methods=['DELETE'])
def delete_snapshot(snapshot_id):
    snapshot = Snapshot.query.get(snapshot_id)
    if snapshot is None:
        return jsonify({"message": "Snapshot not found"}), 404
    db.session.delete(snapshot)
    db.session.commit()
    return jsonify({"message": "Snapshot deleted successfully"}), 200

def compute_aggregated_data():
    aggregated_data = defaultdict(list)
    all_data = UserData.query.all()
    for entry in all_data:
        user_data = eval(entry.data)
        for character, value in user_data['Character'].items():
            aggregated_data[character].append(value)
    return aggregated_data

@app.route('/list_snapshots', methods=['GET'])
def list_snapshots():
    snapshots = Snapshot.query.order_by(Snapshot.month.desc()).all()
    snapshots_list = [snapshot.to_dict() for snapshot in snapshots]
    return jsonify(snapshots=snapshots_list), 200

if __name__ == '__main__':
    with app.app_context():
        init_db()
    app.run(debug=True)
