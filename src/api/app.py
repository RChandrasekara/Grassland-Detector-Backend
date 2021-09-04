import io
import os
import json
import traceback
from datetime import datetime
from urllib.request import urlopen
import bcrypt
import cloudinary
import cloudinary.uploader
import cv2 as cv
import numpy as np
from PIL import Image
from flask import Flask, Response
from flask import flash
from flask import jsonify
from flask import request
from flask_cors import CORS
from flask_jwt_extended import JWTManager
from flask_jwt_extended import create_access_token
from flask_sqlalchemy import SQLAlchemy


UPLOAD_FOLDER = '../../maps'
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'png', 'jpg', 'jpeg', 'gif'}

app = Flask(__name__)
CORS(app)
jwt = JWTManager(app)

app.secret_key = os.getenv("APP_SECRET_KEY")

app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET_KEY")
# app.config["SQLALCHEMY_DATABASE_URI"]="postgresql://postgres:Rukantha123@localhost:5432/Grassland"
app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("SQLALCHEMY_DATABASE_URI")
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = True
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER

cloudinary.config(cloud_name=os.getenv("CLOUD_NAME"),
                  api_key=os.getenv("CLOUDINARY_API_KEY"),
                  api_secret=os.getenv("CLOUDINARY_API_SECRET"))

db = SQLAlchemy(app)
db.init_app(app)


class User(db.Model):
    __tablename__ = 'user'
    id = db.Column(db.Integer, primary_key=True)
    first_name = db.Column(db.String, unique=True, nullable=False)
    last_name = db.Column(db.String, unique=True, nullable=False)
    email = db.Column(db.String, unique=True, nullable=False)
    password = db.Column(db.String, unique=True, nullable=False)

    def __init__(self, first_name, last_name, email, password):
        self.first_name = first_name
        self.last_name = last_name
        self.email = email
        self.password = password

    def to_json(self):
        data = {
            'id': self.id,
            'firstName': self.first_name,
            'lastName': self.last_name,
            'email': self.email,
            'password': self.password
        }

        return jsonify(data)


class Search(db.Model):
    __tablename__ = 'search'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('user.id'))
    search_time = db.Column(db.DateTime, unique=False, nullable=False)
    request_map = db.Column(db.String, unique=False, nullable=True)
    result_map = db.Column(db.String, unique=False, nullable=True)

    def __init__(self, user_id, search_time, request_map, result_map):
        self.user_id = user_id
        self.search_time = search_time
        self.request_map = request_map
        self.result_map = result_map

    def to_json(self):
        data = {
            'id': self.id,
            'userId': self.user_id,
            'searchTime': self.search_time,
            'requestMap': self.request_map,
            'resultMap': self.result_map
        }

        return jsonify(data)


@app.route("/login", methods=["POST"])
def login():
    email = request.json.get("email", None)
    password = request.json.get("password", None)

    query_result = User.query.filter_by(email=email).all()

    if query_result:
        user = {
            'id': query_result[0].id,
            'firstName': query_result[0].first_name,
            'lastName': query_result[0].last_name,
            'email': query_result[0].email
        }

        if bcrypt.checkpw(password.encode('utf-8'), hashed_password=query_result[0].password.encode('utf-8')):
            access_token = create_access_token(identity=email)
            user['token'] = access_token
            return jsonify(user)
        else:
            return jsonify({"msg": "Bad username or password"}), 401
    else:
        return jsonify({"msg": "User not found"}), 404


@app.route("/sign-in", methods=["POST"])
def sign_in():
    first_name = request.json.get("firstName", None)
    last_name = request.json.get("lastName", None)
    email = request.json.get("email", None)
    password = request.json.get("password", None)

    hashed_password = bcrypt.hashpw(password.encode('utf-8'), bcrypt.gensalt())

    if email == "test@test.com" or password == "test":
        return jsonify({"msg": "Bad username or password"}), 401
    try:
        new_user = User(first_name=first_name, last_name=last_name, email=email,
                        password=hashed_password.decode('utf-8'))
        db.session.add(new_user)
        db.session.commit()

        access_token = create_access_token(identity=email)

        user = {
            'id': new_user.id,
            'firstName': new_user.first_name,
            'lastName': new_user.last_name,
            'email': new_user.email,
            'token': access_token
        }
        return jsonify(user)
    except Exception:
        print(traceback.format_exc())
        return jsonify({"msg": "Internal server error"}), 500


@app.route("/users", methods=["GET"])
def show_users():
    users = User.query.all()
    response = []
    for item in users:
        user = {
            'id': item.id,
            'firstName': item.first_name,
            'lastName': item.last_name,
            'email': item.email,
            'password': item.password
        }
        response.append(json.dumps(user))
    response = Response(response, status=200, mimetype="application/json")
    return response


# get contours
def get_contours(img, imgContour):
    contours, Hierarchy = cv.findContours(img, cv.RETR_EXTERNAL, cv.CHAIN_APPROX_NONE)
    for cnt in contours:
        area = cv.contourArea(cnt)
        if area > 50:
            cv.drawContours(imgContour, cnt, -1, (0, 0, 255), 2)
            perimeter = cv.arcLength(cnt, True)
            approx = cv.approxPolyDP(cnt, 0.02 * perimeter, True)


def process_image(roadMap, ndviMap):

    req_road = urlopen(roadMap)
    image = np.asarray(bytearray(req_road.read()), dtype="uint8")
    img = cv.imdecode(image, cv.IMREAD_COLOR)

    req_ndvi = urlopen(ndviMap)
    image = np.asarray(bytearray(req_ndvi.read()), dtype="uint8")
    imgCopy = cv.imdecode(image, cv.IMREAD_COLOR)

    imgHSV = cv.cvtColor(img, cv.COLOR_BGR2HSV)
    lower = np.array([42, 197, 245])
    upper = np.array([84, 255, 255])
    mask = cv.inRange(imgHSV, lower, upper)
    imgGreen = cv.bitwise_and(img, img, mask=mask)
    imgGray = cv.cvtColor(imgGreen, cv.COLOR_BGR2GRAY)
    imgBlur = cv.GaussianBlur(imgGray, (7, 7), 1)
    imgCanny = cv.Canny(imgBlur, 50, 50)
    get_contours(imgCanny, imgCopy)
    return imgCopy


@app.route("/get-location", methods=["POST"])
def upload_file():
    if request.method == 'POST':
        user_id = dict(request.form).get('userId')
        maps = request.files.getlist('images')
        if len(maps) != 2:
            flash('No file part')
            response = {
                "message": "No file part"
            }
            response = Response(json.dumps(response), status=200, mimetype="application/json")
            return response
        if len(maps) == 2 and user_id:
            try:
                road_map = cloudinary.uploader.upload(maps[0])
                ndvi_map = cloudinary.uploader.upload(maps[1])
                grassland_map = process_image(road_map['secure_url'], ndvi_map['secure_url'])
                cv.imwrite('../../maps/processed_road_map.png', grassland_map)
                temp = Image.open('../../maps/processed_road_map.png')
                img_byte_arr = io.BytesIO()
                temp.save(img_byte_arr, format='PNG')
                img_byte_arr = img_byte_arr.getvalue()
                road_map_processed = cloudinary.uploader.upload(img_byte_arr)

                new_search = Search(user_id=int(user_id[0]), search_time=datetime.now(), request_map=ndvi_map['secure_url'],
                                    result_map=road_map_processed['secure_url'])
                db.session.add(new_search)
                db.session.commit()

                response = {
                    "result": road_map_processed['secure_url']
                }

                response = Response(json.dumps(response), status=200, mimetype="application/json")

                return response

            except Exception:
                print(traceback.format_exc())
                return jsonify({"msg": "Internal server error"}), 500
        response = {
            "message": "Invalid data"
        }
        response = Response(json.dumps(response), status=200, mimetype="application/json")
        return response


@app.route("/prev-search", methods=["POST"])
def get_previous_searches():
    if request.method == 'POST':
        user_id = request.json.get("userId", None)
        user = User.query.filter_by(id=user_id).first()
        if user is not None:
            response = []
            search_history = Search.query.filter_by(user_id=user_id).all()
            if search_history:
                for item in search_history:
                    search = {
                        'id': item.id,
                        'searchTime': str(item.search_time),
                        'requestMap': item.request_map,
                        'resultMap': item.result_map
                    }
                    response.append(search)
                return jsonify(response)
            else:
                response = json.dumps(response)
                response = Response(response, status=200, mimetype="application/json")
                return response
        response = {
            "message": "user not found"
        }
        response = Response(json.dumps(response), status=401, mimetype="application/json")
        return response


@app.route("/prev-search", methods=["DELETE"])
def delete_previous_searches():
    if request.method == 'DELETE':
        user_id = request.json.get("userId", None)
        search_id = request.json.get("searchId", None)
        user = User.query.filter_by(id=user_id).first()
        search = Search.query.filter_by(id=search_id).first()
        if user is not None and search is not None:
            db.session.delete(search)
            db.session.commit()
            response = {
                "message": "deleted"
            }
            response = Response(json.dumps(response), status=200, mimetype="application/json")
            return response
        else:
            response = {
                "message": "not found"
            }
            response = Response(json.dumps(response), status=404, mimetype="application/json")
            return response


if __name__ == "__main__":
    app.run(debug=True)
