from flask import Flask, render_template, request, redirect, session, jsonify, send_from_directory
import yaml
from yaml.loader import SafeLoader
from pymongo import *
from pymongo import MongoClient
import uuid
import re
from werkzeug.security import generate_password_hash, check_password_hash
import os
import pickle
from googleapiclient.discovery import build
from google_auth_oauthlib.flow import InstalledAppFlow
from google.auth.transport.requests import Request
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
import base64
from datetime import datetime, timedelta
import matplotlib.pyplot as plt
import requests
import jwt
import urllib.request
import threading
from PIL import Image
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.interval import IntervalTrigger
from flask_sqlalchemy import SQLAlchemy
import json
from flask_caching import Cache
from flask_compress import Compress


# Load config.yaml
with open('config.yaml') as f:
    config = yaml.load(f, Loader=SafeLoader)

task_statuses = {}

# Flask app setup

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'
app.jinja_env.globals.update(zip=zip)

app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///whiteboard.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
whiteboarddb = SQLAlchemy(app)

cache = Cache(app, config={
    'CACHE_TYPE': 'simple',
    'CACHE_DEFAULT_TIMEOUT': 300
})

Compress(app)

class Whiteboard(whiteboarddb.Model):
    id = whiteboarddb.Column(whiteboarddb.Integer, primary_key=True)
    data = whiteboarddb.Column(whiteboarddb.Text)

# MongoDB connection
def vapedetectors():
    cluster = MongoClient(config['mongodbaddress'], connect=False)
    db = cluster["RKingIndustries"]
    vapedetectorsdb = db["vapedetectors"]
    return vapedetectorsdb

def unverified_accounts():
    cluster = MongoClient(config['mongodbaddress'], connect=False)
    db = cluster["RKingIndustries"]
    uvaccountsdb = db["unverified_accounts"]
    return uvaccountsdb

def accounts():
    cluster = MongoClient(config['mongodbaddress'], connect=False)
    db = cluster["RKingIndustries"]
    accountsdb = db["accounts"]
    return accountsdb

def messages():
    cluster = MongoClient(config["mongodbaddress"], connect=False)
    return cluster["RKingIndustries"]["messages"]

def boards():
    cluster = MongoClient(config["mongodbaddress"], connect=False)
    return cluster["RKingIndustries"]["boards"]

def database():
    cluster =MongoClient(config['mongodbaddress'], connect=False)
    db=cluster['improvedbeehive']
    userdata=db['userdata']
    return userdata

def leaderboarddb():
    cluster =MongoClient(config['mongodbaddress'], connect=False)
    db=cluster['improvedbeehive']
    leaderboarddata=db['leaderboard']
    return leaderboarddata

def forums():
    cluster = MongoClient(config['mongodbaddress'], connect=False)
    db = cluster["RKingIndustries"]
    forumsdb = db["forums"]
    return forumsdb

#email  

class GMailDeleter:
    def __init__(self):
        print('User Created')
        self.scopes = ['https://mail.google.com/']
        creds = None
        if os.path.exists('static/token-delete.pickle'):
            with open('static/token-delete.pickle', 'rb') as token:
                creds = pickle.load(token)
        try:
            if not creds or not creds.valid:
                if creds and creds.expired and creds.refresh_token:
                    creds.refresh(Request())
                else:
                    flow = InstalledAppFlow.from_client_secrets_file('static/credentials.json', self.scopes)
                    creds = flow.run_local_server(port=0)
                    with open('static/token-delete.pickle', 'wb') as token:
                        pickle.dump(creds, token)
            self.service = build('gmail', 'v1', credentials=creds)
        except Exception as error:
            print("Error occured while authenticating :-")
            print(error)
        print('GMail API auth completed')
        
    def send_email(self, msg, sendto, subject, type, attachment_location=None):
        emailMsg = msg
        mimeMessage = MIMEMultipart()
        mimeMessage['to'] = sendto
        mimeMessage['subject'] = subject
        mimeMessage.attach(MIMEText(emailMsg, type, 'utf-8'))

        if attachment_location:
            filename = os.path.basename(attachment_location)
            with open(attachment_location, 'rb') as attachment_file:
                attachment_data = attachment_file.read()
            attachment = MIMEText(attachment_data, 'plain', 'utf-8')
            attachment.add_header('Content-Disposition', f'attachment; filename={filename}')
            mimeMessage.attach(attachment)
        raw_string = base64.urlsafe_b64encode(mimeMessage.as_bytes()).decode()
        message = self.service.users().messages().send(userId='me', body={'raw': raw_string}).execute()
        return message

#functions

def credentialscheck(email,password):
    confirmedemail=False
    confirmedpassword=False
    regex = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
    if(re.search(regex,email)):   
        confirmedemail=True
    else:   
        confirmedemail='Please enter a real email address'
    length_error = len(password) < 8
    digit_error = re.search(r"\d", password) is None
    uppercase_error = re.search(r"[A-Z]", password) is None
    lowercase_error = re.search(r"[a-z]", password) is None
    symbol_error = re.search(r"\W", password) is None
    if not ( length_error or digit_error or uppercase_error or lowercase_error or symbol_error ):
        confirmedpassword=True
    else:
        if length_error==True:
            confirmedpassword='Password must be 8 or more charictors.'
        elif digit_error==True:
            confirmedpassword='Password must containe at least one number.'
        elif uppercase_error==True:
            confirmedpassword='Password must containe at least one uppercase letter.'
        elif lowercase_error==True:
            confirmedpassword='Password must containe at least one lowercase letter.'
        elif symbol_error==True:
            confirmedpassword='Password must containe at least one symbol.'
    return confirmedemail, confirmedpassword

def confermationemail(email, code, resend=False):
    with open('config.yaml','r') as yamlfile:
        ymaldata = yaml.safe_load(yamlfile) 
    message = f"""
Dear User,

Thank you for registering with RKing Industries!

To complete your account setup, please visit the following link: 
{ymaldata['website']}/verify

and enter the code: {code}

If you did not create this account, please ignore this email.

Best regards,  
RKing Industries Team
"""
    if resend == True:
        message = f"""
Dear User,

You have requested to resend the verification email.  
To complete your account setup, please click the verification link below:

{ymaldata['website']}/verify/{code}

or visit {ymaldata['website']}/verify  
and enter the code: {code}

If you did not create this account, please ignore this email.

Best regards,  
RKing Industries Team
"""
    user = GMailDeleter()
    user.send_email(message, email, 'Verifcation Email', 'plain')   

def checkdelta(given_datetime_str):
    given_datetime = datetime.strptime(given_datetime_str, "%d-%m-%Y %H:%M")
    current_datetime = datetime.now()
    one_hour = timedelta(minutes=30)
    if current_datetime > given_datetime + one_hour:
        return True
    else:
        return False
    
def graph(apikey):
    vapedetectorsdb=vapedetectors()
    document = vapedetectorsdb.find_one({apikey: {"$exists": True}})
    if document:
        issues=document[apikey]['history']
        data={}
        for issue_key, issue_details in issues.items():
            data[issue_key] = issue_details
        rooms = list(data.keys())
        values = list(data.values())
        total = sum(values)
        percentages = [f'{(v / total * 100):.1f}%' for v in values]
        labels_with_details = [f'{room}: {v} ({percentage})' for room, v, percentage in zip(rooms, values, percentages)]
        fig, ax = plt.subplots(figsize=(8, 8), facecolor='none')
        wedges, _ = ax.pie(
            values, 
            colors=plt.cm.Paired(range(len(rooms))),
            startangle=140,  
            wedgeprops=dict(width=0.3)  
        )
        ax.legend(
            wedges,
            labels_with_details,
            title="Rooms",
            loc="center left",
            bbox_to_anchor=(1, 0, 0.5, 1),  
            fontsize=14, 
          title_fontsize=16 
        )
        ax.set_facecolor('none')
        fig.patch.set_facecolor('none')
        plt.gca().set_title('')  
        plt.tight_layout()
        plt.savefig(f'static/graphs/{apikey}.png')

def submit_assighment(token,id,ass):
    url = f'https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/students/{id}/assignments/{ass}/submit'
    headers = {
        'Accept': '*/*',
        'Accept-Encoding': 'gzip, deflate, br, zstd',
        'Accept-Language': 'en-GB,en;q=0.9,en-US;q=0.8',
        'Access-Control-Request-Headers': 'authorization,content-type,x-client-version-desktop',
        'Access-Control-Request-Method': 'POST',
        'Connection': 'keep-alive',
        'Host': 'beehiveapi.lionhearttrust.org.uk',
        'Origin': 'https://beehive.lionhearttrust.org.uk',
        'Referer': 'https://beehive.lionhearttrust.org.uk/',
        'Sec-Fetch-Dest': 'empty',
        'Sec-Fetch-Mode': 'cors',
        'Sec-Fetch-Site': 'same-site',
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/128.0.0.0 Safari/537.36 Edg/128.0.0.0'
    }

    response = requests.options(url, headers=headers)
    if response.status_code==200:
        url = f'https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/students/{id}/assignments/{ass}/submit'
        headers = {
            'Authorization': f'Bearer {token}'
        }
        data = {
            "difficulty": None,
            "timescale": None,
            "comments": None,
            "requireAssistance": None,
            "understoodRequirements": None,
            "studentId": id,
            "assignmentId": ass
        }
        response = requests.post(url, headers=headers, json=data)
        if response.status_code==200:
            return True
        else:
            return False
    else:
        return False

def smartcard(token, id):
    url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/payments/users/{id}/smartcards/all"
    url2=f'https://beehiveapi.lionhearttrust.org.uk/v3.5/payments/users/{id}/smartcards/transactions?pageIndex=0&pageSize=1000'
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        response2 = requests.get(url2, headers=headers)
        if response2.status_code == 200:
            transactions=[]
            for i in response2.json()['items']:
                transactions.append({'total':i['total'],'description':i['description'],'date':i['date']})
        balance=(response.json()[0]['balance'])
        printbalance=(response.json()[0]['printCreditBalance']['purses'][1]['balance'])
        return balance, printbalance,transactions
    else:
        return False

def get_stats(token,id):
    import requests
    url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/students/{id}"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        tutorGroup=response.json()['tutorGroup']['name']
        name=(f"{response.json()['firstName']} {response.json()['lastName']}")
        attendance=(response.json()['pastoral']['attendance'])
        behaviourPoints=(response.json()['pastoral']['behaviourPoints'])
        rewardPoints=(response.json()['pastoral']['rewardPoints'])
        lates=(response.json()['pastoral']['lates'])
        absences=(response.json()['pastoral']['absences'])

        return name,tutorGroup,attendance,behaviourPoints,rewardPoints,lates,absences
    else:
        return False

def events(token,id):
    url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/calendar/users/{id}/events"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    now = datetime.now()
    formatted_date = now.strftime("%Y-%m-%d")
    params = {
        "pageIndex": 0,
        "startDate": formatted_date
    }

    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        def reformat_json(data):
            formatted_data = {}
            for item in data['items']:
                formatted_data[str(item['id'])] = {
                    'title': item['title'],
                    'allowsignupfrom': item['allowSignupFrom'],
                    'allowsighnupto': item.get('allowSignupTo', 'N/A'), 
                    'sighnedup': item['signedUp']
                }
            return formatted_data
        formatted_data = reformat_json(response.json())
        return formatted_data 
    else:
        return False


def fetch_timetable(token,id):
    url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/users/{id}/timetable"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        parsed_data = {}
        for school in (response.json())['schools']:
            for cycle in school['cycles']:
                for day in cycle['days']:
                    day_name = day['day']
                    parsed_data[day_name] = {}
                    lunch=False
                    offset=1
                    for idx, lesson in enumerate(day['lessons']):
                        end_time=lesson['ends']
                        start_time=lesson['starts']
                        if lesson['teacher'].strip():
                            subject = lesson['subject']
                        else:
                            if idx == 5:
                                subject='Lunch'
                                lunch=True
                            elif idx == 6 and lunch == False:
                                subject='Lunch'
                                end_time = '14:00:00'
                                start_time='13:20:00'
                                lunch=True
                            else:
                                subject = 'Free'
                            
                            
                        if idx == 5 and lunch==False:
                            end_time='13:20:00'
                        if idx==3:
                            parsed_data[day_name][str(idx+offset)] = {
                            'subject': 'break',
                            'teacher': '',
                            'room': '',
                            'times': f"10:30:00 to 10:50:00"

                        }
                            offset=2
                        teacher = lesson['teacher'].strip() if lesson['teacher'].strip() else ''
                        try:
                            room = lesson['room'].strip() if lesson['room'].strip() else ''
                        except:
                            room=''
                        parsed_data[day_name][str(idx+offset)] = {
                            'subject': subject,
                            'teacher': teacher,
                            'room':room,
                            'times': f"{start_time} to {end_time}"

                        }
        
        return parsed_data
    else:
        return False

def get_assighments(token,id):
    url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/students/{id}/assignmentstiny"
    params = {
        "filter": "0",
        "pageSize": "1000",
        "pageIndex": "0"
    }
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers, params=params)
    if response.status_code == 200:
        formatted_data = {}
        for item in response.json()['items']:
            url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/users/{id}/assignments/{item['id']}"
            headers = {
                "Authorization": f"Bearer {token}"
            }
            response = requests.get(url, headers=headers)
            if response.status_code == 200:
                files={}
                links=[]
                for i in response.json()['files']:
                    files[str(i['id'])]=i['filename']
                for i in response.json()['links']:
                    links.append(i['url'])
                formatted_data[str(item['id'])] = {
                    "title": response.json()['title'],
                    "deadline": response.json()['deadline'],
                    "set_by": f"{response.json()['setBy']['title']} {response.json()['setBy']['firstName']} {response.json()['setBy']['lastName']}",
                    "completed": response.json()['isComplete'],
                    "overdue": response.json()['isOverdue'],
                    "description": response.json()['details'],
                    "links":links,
                    "files":files
                }
        return formatted_data
    else:
        return False

def links(token):
    url = "https://beehiveapi.lionhearttrust.org.uk/v3.5/planner/links"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        data=response.json()
        output_data = {}
        for category in data:
            for link in category['links']:
                output_data[link['title']] = {
                    'desk': link['description'],
                    'url': link['url']
                }
        return output_data
    return False

def noticeboard(token,id):
    url = f"https://beehiveapi.lionhearttrust.org.uk/v3.5/feed/users/{id}?feedItemType=1&pageIndex=0&pageSize=20"
    headers = {
        "Authorization": f"Bearer {token}"
    }
    response = requests.get(url, headers=headers)
    if response.status_code == 200:
        parsed_data=[]
        for i in response.json()['items']:
            images=[]
            for j in i['files']:
                if j['extension'] == '.png' or j['extension'] == '.jpeg' or j['extension'] == '.jpg':
                    print('1')
                    images.append(j['id'])
                    if not os.path.isfile(f'static/beehive/{j["id"]}.jpg'):
                        
                        def download_image(url, save_as):
                            urllib.request.urlretrieve(url, save_as)
                        image_url = f'https://beehiveapi.lionhearttrust.org.uk/v3.5/files/images/{j["id"]}'
                        save_as = f'static/beehive/{j["id"]}.jpg'
                        download_image(image_url, save_as)
                        jpg_image = Image.open(save_as)
                        jpg_image.save(f'static/beehive/{j["id"]}.webp', 'WEBP', quality=50) 
                        os.remove(save_as)
            parsed_data.append({'title':i['title'],'content':i['content'],'images':images,'time':i['publishedDate']})
        return parsed_data
    else:
        return False


def leaderboard():
    datas = database()  
    data=datas.find()
    people = []
    for i in data:
        for person_id, person_data in i.items():
            if person_id != "_id":
                people.append({
                    "name": person_data["name"],
                    "form": person_data["tutorGroup"],
                    "rewardPoints": person_data["rewardPoints"],
                    "behaviourPoints": person_data["behaviourPoints"]
                })
    top_reward_points = sorted(people, key=lambda x: x["rewardPoints"], reverse=True)[:20]
    top_behaviour_points = sorted(people, key=lambda x: x["behaviourPoints"], reverse=True)[:20]
    leader=leaderboarddb()
    leader.update_one(
        {'top_behaviour_points': {'$exists': True}},
        {'$set': {'top_behaviour_points': top_behaviour_points}},
        upsert=True
    )
    leader.update_one(
        {'top_reward_points': {'$exists': True}},
        {'$set': {'top_reward_points': top_reward_points}},
        upsert=True
    )



def fetchall(token,id,username,password):
    print('stated')
    try:
        try:
            args=smartcard(token,id)
            if args != False:
                balance=(args[0]) 
                print_balance=(args[1]) 
                transactions=(args[2]) 
            else:
                args=smartcard(token,id)
                if args != False:
                    balance=(args[0]) 
                    print_balance=(args[1])
                    transactions=(args[2])
                else:
                    balance=0
                    print_balance=0
                    transactions={}
        except:
            print('smartcard failed')
            balance=0
            print_balance=0
            transactions={}
        try:
            args=get_stats(token,id)
            if args != False:
                name = args[0]
                tutorGroup = args[1]
                attendance = args[2]
                behaviourPoints = args[3]
                rewardPoints = args[4]
                lates = args[5]
                absences = args[6]
            else:
                args=get_stats(token,id)
                if args != False:
                    name = args[0]
                    tutorGroup = args[1]
                    attendance = args[2]
                    behaviourPoints = args[3]
                    rewardPoints = args[4]
                    lates = args[5]
                    absences = args[6]
                else:
                    name = 'unknown'
                    tutorGroup = 'unknown'
                    attendance = 0
                    behaviourPoints = 0
                    rewardPoints = 0
                    lates = 0
                    absences = 0
        except:
            print('stats failed')
            name = 'unknown'
            tutorGroup = 'unknown'
            attendance = 0
            behaviourPoints = 0
            rewardPoints = 0
            lates = 0
            absences = 0
        try:
            args=fetch_timetable(token,id)
            if args != False:
                timetable=args
            else:
                args=fetch_timetable(token,id)
                if args != False:
                    timetable=args
                else:
                    timetable={}
        except:
            print('timetable failed')
            timetable={}
        try:
            args=get_assighments(token,id)
            if args != False:
                assighments=args
            else:
                args=get_assighments(token,id)
                if args != False:
                    assighments=args
                else:
                    assighments={}
        except:
            print('assighments failed')
            assighments={}
        try:
            args=links(token)
            if args != False:
                link=args
            else:
                args=links(token)
                if args != False:
                    link=args
                else:
                    link={}
        except:
            print('links failed')
            link={}
        try:
            args=events(token,id)
            if args != False:
                event=args
            else:
                args=events(token,id)
                if args != False:
                    event=args
                else:
                    event={}
        except:
            print('envents failed')
            event={}
        try:
            args=noticeboard(token,id)
            if args != False:
                noticebord=args
            else:
                args=noticeboard(token,id)
                if args != False:
                    noticebord=args
                else:
                    noticebord={}
        except:
            print('noticeboard failed')
            noticebord={}
        databasedb=database()
        find=databasedb.find_one({str(id): {'$exists': True}})
        if find == None or find == '':
            try:  
                databasedb.insert_one({
                        str(id):{
                            'username':username,
                            'password':password,
                            'name':name,
                            'tutorGroup':tutorGroup,
                            'balance':balance,
                            'printbalance':print_balance,
                            'attendance':attendance,
                            'behaviourPoints':behaviourPoints,
                            'rewardPoints':rewardPoints,
                            'lates':lates,
                            'absences':absences,
                            'timetable':timetable,
                            'assighments':assighments,
                            'links':link,
                            'events':event,
                            'transactions':transactions,
                            'noticeboard':noticebord
                            }
                        })
                message = """
Dear User,

Great news! Your Beehive account has been successfully linked.

Best regards,  
RKing Industries Team
"""
                logged_accounts=accounts()
                account = logged_accounts.find_one({'bhid':id})
                user = GMailDeleter()
                user.send_email(message, account['email'], 'Beehive Linked', 'plain')
            except Exception as e:
                print(e)
        else:
            try:
                databasedb.update_one({str(id): {'$exists': True}},
            {'$set': {str(id): {
                        'username':find[str(id)]['username'],
                        'password':find[str(id)]['password'],
                        'name':name,
                        'tutorGroup':tutorGroup,
                        'balance':balance,
                        'printbalance':print_balance,
                        'attendance':attendance,
                        'behaviourPoints':behaviourPoints,
                        'rewardPoints':rewardPoints,
                        'lates':lates,
                        'absences':absences,
                        'timetable':timetable,
                        'assighments':assighments,
                        'links':link,
                        'events':event,
                        'transactions':transactions,
                        'noticeboard':noticebord
                    }}},
                upsert=True
                )
            except Exception as e:
                print(e)
    except:
        pass

    leaderboard()

    task_statuses[id] = True


@app.route('/submit/<ass>')
def submit(ass):
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
            return redirect('/login')
        try:
            link=account['beehivelinked']
        except:
            link=False
        if link == False:
            return render_template('notlincked.html')
        id=account['bhid']
        token=account['bhtoken']
        logins=database()
        found=logins.find_one({id: { '$exists' : True } })
        if found:
            data=submit_assighment(token,id,ass)
            print(data)
            if data == True:
                result = logins.update_one(
                    {id: {'$exists': True}},
                    {"$set": {f"{id}.assighments.{ass}.completed": True}}
                )
                print(result)
        
        return jsonify({'success': True})
    return redirect('/login')

def rescan():
    logins=database()
    data=logins.find()

    for doc in data:
        _id = doc.get('_id')
        for key, value in doc.items():
            if isinstance(value, dict):
                username = value.get('username')
                password = value.get('password')
                if username and password:
                    response = fasthivelogin(username,password)
                    if response != False:
                        fetchall(response[0],response[1],None,None)
                    else:
                        response = fasthivelogin(username,password)
                        if response != False:
                            fetchall(response[0],response[1],None,None)
                        else:
                            pass
    task_statuses[id] = True


# Schedule the rescan job to run every 1/2 hour

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=rescan,
    trigger=IntervalTrigger(hours=0.5),
    id='rescan_job',
    name='Rescan database every hour',
    replace_existing=True
)
scheduler.start()

# Routes

@app.route('/')
@cache.memoize(timeout=60)
def index():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        else:
            try:
                account['beehivelinked']
                link=True
            except:
                link=False
            return render_template('index.html', loggedin=True, link=link)
    return render_template('index.html')

@app.route('/devlog')
@cache.memoize(timeout=60)
def devlog():
    return render_template('devlog.html')

@app.route('/dartsgame')
@cache.memoize(timeout=60)
def dartsgame():
    return render_template('dartsgame.html')

@app.route('/game')
@cache.memoize(timeout=60)
def game():
    return render_template('game.html')

@app.route('/store')
@cache.memoize(timeout=60)
def store():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
    return render_template('store.html', products=config['products'])

@app.route('/vapedetectors')
@cache.memoize(timeout=60)
def vapedetectorspage():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
    
    return render_template('vapedetectors.html')

@app.route('/fasthiveinfo')
@cache.memoize(timeout=60)
def fasthiveinfo():
    link=False
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        try:
            account['beehivelinked']
            link=True
        except:
            pass
    
    return render_template('info.html', link=link)

@app.route('/contact', methods=['GET', 'POST'])
@cache.memoize(timeout=60)
def contact():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
    if request.method == 'POST':
        name = request.form.get('name')
        email = request.form.get('email')
        subject = request.form.get('subject')
        message = request.form.get('message')
        if not(name==None or email==None or subject==None or message==None or name=="" or email=="" or subject=="" or message == ""):
            body = f"""
            New contact form submission received:
            
            Name: {name}
            Email: {email}
            Subject: {subject}
            Message: {message}
            """
            user = GMailDeleter()
            user.send_email(body, config['supportemail'], 'Contact Request', 'plain')

    return render_template('contact.html', email=config['supportemail'], phone=config['supportphone'])


@app.route('/signup', methods=["GET", "POST"])

def signup():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account != None:
            return redirect('/')
        else:
            session.pop('userid', None)
    elif request.method == 'POST':

        firstname = (str(request.form['firstname'])).lower()
        lastname = (str(request.form['lastname'])).lower()
        email = (str(request.form['email'])).lower()
        username = request.form['username']
        password = request.form['password']
        retypepassword = request.form['retypepassword']
        
        uvaccounts=unverified_accounts()
        vfaccounts=accounts()

        email_check1 = uvaccounts.find_one({'email':email})
        email_check2 = vfaccounts.find_one({'email':email})
        username_check1 = uvaccounts.find_one({'username':username})
        username_check2 = vfaccounts.find_one({'username':username})
        email_data, password_data = credentialscheck(email,password)
 
        if email_check1 != None or email_check2 != None:
            return render_template('signup.html', error='Email allready in use.')
        elif username_check1 != None or username_check2 != None:
            return render_template('signup.html', error='Username allready in use.')
        elif password != retypepassword:
            return render_template('signup.html', error='Passwords do not match.')
        elif email_data != True:
            return render_template('signup.html', error=email_data)
        elif password_data != True:
            return render_template('signup.html', error=password_data)
        else:
            ccode=str(uuid.uuid4())
            hashed_password = generate_password_hash(password, method='pbkdf2:sha256')
            usercredentials = {"username":username, "email":email, "password":hashed_password, 'firstname':firstname, 'lastname':lastname, 'confermationcode':ccode}
            uvaccounts.insert_one(usercredentials)
            confermationemail(email, ccode)
            return redirect('/verify')   
    else:
        return render_template('signup.html')


@app.route('/login', methods=["GET", "POST"])
def login():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account != None:
            redirect_url = request.args.get('next', '/')
            return redirect(redirect_url)
        else:
            session.pop('userid', None)
    if request.method == 'POST':
        logged_accounts=accounts()
        email = (request.form['email']).lower()
        password = request.form['password']
        redirect_url = request.form.get('next', '/')
        print(redirect_url)

        account = logged_accounts.find_one({'email':email})
        if account != None:
            if check_password_hash(account['password'], password):
                session['userid'] = account['userid']
                return redirect(redirect_url)
            else:
                return render_template('login.html', error='Invalid Password', next=redirect_url)
        else:
            unaccounts = unverified_accounts()
            if unaccounts.find_one({'email':email}):
                return redirect('/verify')
            return render_template('login.html', error='Invalid Email', next=redirect_url)

    redirect_url = request.args.get('next', '/')
    print(redirect_url)
    return render_template('login.html', next=redirect_url)




@app.route('/verify', methods=["GET", "POST"])
def verify_page():
    if 'userid' in session:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if account != None:
            return redirect('/')
        else:
            session.pop('userid', None)
            
    if request.method == 'POST':
        if 'code' in request.form:
            code = request.form['code']
            return redirect(f'/verify/{code}')
        elif 'email' in request.form:
            email = request.form['email']
            uvaccounts = unverified_accounts()
            user_data = uvaccounts.find_one({'email': email})
            if user_data:
                confermationemail(email, user_data['confermationcode'], True)
                return render_template('verify.html', message='Verification code resent!')
            return render_template('verify.html', error='Email not found in pending verifications')
            
    return render_template('verify.html')

@app.route('/verify/<confermationcode>', methods=["GET"])
@cache.memoize(timeout=60)
def verify(confermationcode):
    if 'userid' in session:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if account != None:
            return redirect('/')
        else:
            session.pop('userid', None)

    uvaccounts = unverified_accounts()
    vfaccounts = accounts()
    check = uvaccounts.find_one({'confermationcode': confermationcode})
    
    if check != None:
        uvaccounts.delete_one(check)
        apikey=((str(uuid.uuid4()).split('-'))[0]+(str(uuid.uuid4()).split('-'))[1])
        usercredentials = {
            "username": check['username'],
            "email": check['email'],
            "password": check['password'],
            'firsname': check['firstname'],
            'lastname': check['lastname'],
            'userid': str(uuid.uuid4()),
            'apikey': apikey
        }
        vfaccounts.insert_one(usercredentials)
        vapedetectorsdb = vapedetectors()      
        vapedetectorsinsert = {
            apikey: {
                'issues': {}, 
                'status': {}, 
                'history': {}
            },
            'emails': {'0':check['email']}
        }
        vapedetectorsdb.insert_one(vapedetectorsinsert)
        os.makedirs(f"files/{check['username']}")

        user = GMailDeleter()
        message = """
Dear User,

Great news! Your RKing Industries account has been successfully verified.

You can now log in to your account and access all our services at full capacity.

For security purposes, please keep your login credentials safe and never share them with others.

Need help? Our support team is here for you.

Best regards,  
RKing Industries Team
"""
        user.send_email(message, check['email'], 'Account Varified', 'plain')
        return redirect('/login')
    
    return render_template('verify.html', error='Invalid verification code')

@app.route('/vapedetectors/panel', methods=['GET','POST'])
@cache.memoize(timeout=60)
def panel():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        apikey=account['apikey']
        vapedetectorsdb = vapedetectors()
        info = vapedetectorsdb.find_one({apikey: {"$exists": True}})
        if request.method == 'POST':
            try:
                room_name = request.json['room_name']
                
                if room_name in info[apikey]['status']:
                    vapedetectorsdb.update_one(
                        {apikey: {"$exists": True}},
                        {"$unset": {f"{apikey}.status.{room_name}": ""}}
                    )
                    return jsonify({"success": True})
                return jsonify({"success": False})
            except:
                try:
                    email_id = request.json['email_id']
                    if email_id in info['emails']:
                        vapedetectorsdb.update_one(
                            {apikey: {"$exists": True}},
                            {"$unset": {f"emails.{email_id}": ""}}
                        )
                        return jsonify({"success": True})
                    return jsonify({"success": False})
                except:
                    try:
                        new_email = request.json['new_email']
                        email_dict = info.get('emails', {})
                        next_index = str(len(email_dict)) 

                        vapedetectorsdb.update_one(
                            {apikey: {"$exists": True}},
                            {"$set": {f"emails.{next_index}": new_email}}
                        )
                        return jsonify({"success": True})
                    except:
                        try:
                            issue_id = request.json['issue_id']
                            doc = vapedetectorsdb.find_one({apikey: {"$exists": True}})
                            if not doc or "issues" not in doc[apikey] or issue_id not in doc[apikey]["issues"]:
                                return jsonify({"success": False})

                            current_status = doc[apikey]["issues"][issue_id]["resolved"]
                            new_status = not current_status 

                            vapedetectorsdb.update_one(
                                {f"{apikey}.issues.{issue_id}": {"$exists": True}},
                                {"$set": {f"{apikey}.issues.{issue_id}.resolved": new_status}}
                            )

                            return jsonify({"success": True})

                        


                        except:
                            return jsonify({"success": False})

        else:
            vapedetectorsdb = vapedetectors()                                                                                                                                                                                 
            find = vapedetectorsdb.find_one({apikey: {"$exists": True}})
            for key, value in find[apikey]['status'].items():
                if value['status'] == 'online':
                    if checkdelta(value['last_ping']):
                        updated_status = {
                            "status": "offline",
                            "last_ping": value['last_ping']
                        }
                        vapedetectorsdb.update_one(
                            {apikey: {"$exists": True}},
                            {"$set": {f"{apikey}.status.{key}": updated_status}}
                        )
                        emails=vapedetectorsdb.find_one({apikey: {"$exists": True}})
                        for _, email in (emails['emails']).items():
                            user = GMailDeleter()
                            message = f"""
Alert: Device Offline  
Device Location: {key}  
Status: No telemetry ping received  
Time Elapsed: >30 minutes  
Last Known Ping: {value['last_ping']}

Please check the device connection and status. If issues persist, contact technical support.
"""
                            user.send_email(message, email, "Offline" , 'plain') 
    
        return render_template('panel.html', status=info[apikey]['status'], emails=info['emails'], issues=info[apikey]['issues'],apikey=apikey)

    return redirect('/login?next=/panel')

@app.route('/api', methods=["GET", "POST"])
def api():
    if request.method == 'POST':
        data = request.get_json()
        errors = {}
        if not data or 'api_key' not in data:
            errors['api_key'] = "API key missing"

        if 'type' not in data:
            errors['type'] = "Type of message missing"

        if errors != {}:
            return jsonify(errors), 400
        
        api_key = data['api_key']
        vapedetectorsdb = vapedetectors()                                                                                                                                                                                 
        find = vapedetectorsdb.find_one({api_key: {"$exists": True}})
        if find == None:
            return jsonify({'api_key': 'Invalid API key'}), 400
        for key, value in find[api_key]['status'].items():
            if value['status'] == 'online':
                if checkdelta(value['last_ping']):
                    updated_status = {
                        "status": "offline",
                        "last_ping": value['last_ping']
                    }
                    vapedetectorsdb.update_one(
                        {api_key: {"$exists": True}},
                        {"$set": {f"{api_key}.status.{key}": updated_status}}
                    )
                    emails=vapedetectorsdb.find_one({api_key: {"$exists": True}})
                    for _, email in (emails['emails']).items():
                        user = GMailDeleter()
                        user.send_email(f"""{key} has not sent a telemetry ping in more then 30 minuets.""", email, "Offline" , 'plain') 


        typeofmessage=data['type']
        
        if typeofmessage == 'send':
            if 'reason' not in data:
                errors['reason'] = "Reason of api request missing"

            if 'room' not in data:
                errors['room'] = "Room not provided"

            if errors != {}:
                return jsonify(errors), 400

            room = data['room']
            reason = data['reason']

            if reason == 'vape':
                doc = vapedetectorsdb.find_one({api_key: {"$exists": True}})

                if doc and "issues" in doc[api_key]:
                    issue_ids = list(doc[api_key]["issues"].keys())
                    try:
                        highest_issue_id = max(map(int, issue_ids))
                        new_issue_id = str(highest_issue_id + 1)
                    except ValueError as e:
                        new_issue_id = "0"
                else:
                    new_issue_id = "0"

                new_issue = {
                    "room": room,
                    "issue": "vape",
                    "time": f"{str((datetime.now()).strftime('%d-%m-%Y %H:%M'))}",
                    "resolved": False
                }

                vapedetectorsdb.update_one(
                    {api_key: {"$exists": True}},
                    {"$set": {f"{api_key}.issues.{new_issue_id}": new_issue}}
                )

                if doc and "history" in doc[api_key] and room in doc[api_key]["history"]:
                    current_count = doc[api_key]["history"][room]
                    new_count = current_count + 1
                else:
                    new_count = 1

                vapedetectorsdb.update_one(
                    {api_key: {"$exists": True}},
                    {"$set": {f"{api_key}.history.{room}": new_count}}
                )
                emails=vapedetectorsdb.find_one({api_key: {"$exists": True}})
                graph(api_key)
                for _, email in (emails['emails']).items():
                    user = GMailDeleter()
                    message = f"""
Vape Detected:  
Date: {str((datetime.now()).strftime('%d-%m-%Y'))}  
Time: {str((datetime.now()).strftime('%H:%M'))}  
Room: {room}
"""

                    user.send_email(message, email, "Vape Detected" , 'plain') 
                updated_status = {
                    "status": "online",
                    "last_ping": f"{str((datetime.now()).strftime('%d-%m-%Y %H:%M'))}"
                }
                vapedetectorsdb.update_one(
                    {api_key: {"$exists": True}},
                    {"$set": {f"{api_key}.status.{room}": updated_status}}
                )

                find = vapedetectorsdb.find_one({f"{api_key}.status.{room}": {"$exists": True}})
            elif reason == 'tamper':
                doc = vapedetectorsdb.find_one({api_key: {"$exists": True}})

                if doc and "issues" in doc[api_key]:
                    issue_ids = list(doc[api_key]["issues"].keys())
                    try:
                        highest_issue_id = max(map(int, issue_ids))
                        new_issue_id = str(highest_issue_id + 1)
                    except ValueError as e:
                        new_issue_id = "0"
                else:
                    new_issue_id = "0"

                new_issue = {
                    "room": room,
                    "issue": "tamper",
                    "time": f"{str((datetime.now()).strftime('%d-%m-%Y %H:%M'))}",
                    "resolved": False
                }

                vapedetectorsdb.update_one(
                    {api_key: {"$exists": True}},
                    {"$set": {f"{api_key}.issues.{new_issue_id}": new_issue}}
                )

                emails=vapedetectorsdb.find_one({api_key: {"$exists": True}})
                for _, email in (emails['emails']).items():
                    user = GMailDeleter()
                    message = f"""
Tamper Detected:  
Date: {str((datetime.now()).strftime('%d-%m-%Y'))}  
Time: {str((datetime.now()).strftime('%H:%M'))}  
Room: {room}
"""
                    user.send_email(message, email, "Vape Detected" , 'plain') 
                updated_status = {
                    "status": "online",
                    "last_ping": f"{str((datetime.now()).strftime('%d-%m-%Y %H:%M'))}"
                }
                vapedetectorsdb.update_one(
                    {api_key: {"$exists": True}},
                    {"$set": {f"{api_key}.status.{room}": updated_status}}
                )

                find = vapedetectorsdb.find_one({f"{api_key}.status.{room}": {"$exists": True}})

            elif reason == 'ping':

                updated_status = {
                    "status": "online",
                    "last_ping": f"{str((datetime.now()).strftime('%d-%m-%Y %H:%M'))}"
                }
                vapedetectorsdb.update_one(
                    {api_key: {"$exists": True}},
                    {"$set": {f"{api_key}.status.{room}": updated_status}}
                )

                find = vapedetectorsdb.find_one({f"{api_key}.status.{room}": {"$exists": True}})
                if find == None:
                    emails=vapedetectorsdb.find_one({api_key: {"$exists": True}})
                    for _, email in (emails['emails']).items():
                        user = GMailDeleter()
                        message = f"""
New VapeDetector Adopted: {room}  
This device has been added to the panel.
"""

                        user.send_email(message, email, "Device Adopted", 'plain') 
            else:
                return jsonify({"Invalid Reason": "Invalid reason provided"}), 400
            return jsonify({"message": "success"}), 200
        
        elif typeofmessage == 'fetch':
            if 'identity' not in data:
                errors['identity'] = "No identity provided"

            if errors != {}:
                return jsonify(errors), 400

            identity = data['identity']

            if identity == 'issues':
                document = vapedetectorsdb.find_one({api_key: {"$exists": True}})
                if document:
                    issues=document[api_key]['issues']
                    return_issues={}
                    for issue_key, issue_details in issues.items():
                        return_issues[issue_key] = dict(issue_details)
                    return jsonify({"Issues": return_issues}), 200
            
            elif identity == 'status':
                document = vapedetectorsdb.find_one({api_key: {"$exists": True}})
                if document:
                    issues=document[api_key]['status']
                    return_issues={}
                    for issue_key, issue_details in issues.items():
                        print(issue_details)
                        return_issues[issue_key] = dict(issue_details)
                    return jsonify({"status": return_issues}), 200
                
            elif identity == 'history':
                document = vapedetectorsdb.find_one({api_key: {"$exists": True}})
                if document:
                    issues=document[api_key]['history']
                    return_issues={}
                    for issue_key, issue_details in issues.items():
                        return_issues[issue_key] = issue_details
                    return jsonify({"history": return_issues}), 200

            else:
                return jsonify({"Invalid Identity": "Invalid identity provided"}), 400
            
        elif typeofmessage == 'toggle':
            if 'issue_id' not in data:
                errors['issue_id'] = "No issue_id provided"
            if errors != {}:
                return jsonify(errors), 400
            try:
                issue_id = data['issue_id']
            except:
                return jsonify({'Issue Error':'Invalid issue id'}), 400
            doc = vapedetectorsdb.find_one({api_key: {"$exists": True}})
            if not doc or "issues" not in doc[api_key] or issue_id not in doc[api_key]["issues"]:
                return jsonify({"error": "Issue not found"}), 404

            current_status = doc[api_key]["issues"][issue_id]["resolved"]
            new_status = not current_status 

            vapedetectorsdb.update_one(
                {f"{api_key}.issues.{issue_id}": {"$exists": True}},
                {"$set": {f"{api_key}.issues.{issue_id}.resolved": new_status}}
            )
            return jsonify({"message": "success"}), 200



        else:
            return jsonify({'Type Error':'Invalid type provided'}), 400
                
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        return render_template('api.html')
        
    return render_template('api.html')











def fasthivelogin(username, password):
    url = "https://beehiveapi.lionhearttrust.org.uk/token"
    payload = {
        'grant_type': 'password',
        'username': username,
        'password': password,
        'client_id': 'web'
    }
    response = requests.post(url, data=payload)
    if response.status_code == 200:
        token=(response.json()['access_token'])
        decoded = (jwt.decode(token, options={"verify_signature": False}))
        id=decoded['id']
        return token,id
    else:
        return False
    










@app.route('/profile', methods=['POST', 'GET'])
@cache.memoize(timeout=60)
def profile():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        else:
            try:
                account['beehivelinked']
                link=False
            except:
                link=True

            if request.method == 'POST':
                if request.form.get('action') == 'change_password':
                    current_password = request.form['current_password']
                    new_password = request.form['new_password']
                    confirm_password = request.form['confirm_password']

                    if new_password != confirm_password:
                        return render_template('profile.html', error='Passwords do not match')
                    _, password_check = credentialscheck("dummy@email.com", new_password)
                    if password_check != True:
                        return render_template('profile.html', error=password_check)
                    if check_password_hash(account['password'], current_password):
                        new_password_hash = generate_password_hash(new_password)
                        logged_accounts.update_one({'userid': session['userid']}, {'$set': {'password': new_password_hash}})
                        return render_template('profile.html', success='Password changed successfully')
                    else:
                        return render_template('profile.html', error='Incorrect current password')
                
                if request.form.get('action') == 'delete_account':
                    password = request.form['password']
                    if check_password_hash(account['password'], password):
                        vpd=vapedetectors()
                        vpd.delete_one({account['apikey']:{ '$exists' : True }})
                        logged_accounts.delete_one({'userid': session['userid']})

                        session.pop('userid', None)
                        return redirect('/')
                    return render_template('profile.html', error3='Invalid password')

                if request.form.get('action') == 'link_beehive':   
                    try:
                        account['beehivelinked']
                        return render_template('profile.html', error2="You have already linked your beehive account",link=False)
                    except:
                        username = request.form['beehive_username']
                        password = request.form['beehive_password']       
                        response = fasthivelogin(username, password)   
                        if response != False:
                            session['username'] = username
                            session['password'] = password
                            account["beehivelinked"] = "True"
                            account["bhtoken"] = response[0]
                            account["bhid"] = response[1]
                            logged_accounts.replace_one({'userid':session['userid']}, account)
                            return redirect('/updating')
                        return render_template('profile.html', error2='Invalid Beehive credentials', link=link)

            return render_template('profile.html',link=link)
    return redirect('/login?next=/profile')





@app.route('/events/<ass>')
@cache.memoize(timeout=60)
def eventss(ass):
    return 'Currently not avalable <a href="/">Home</a> '

@app.route('/fasthive/')
@cache.memoize(timeout=60)
def fasthive():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
            return redirect('/login?next=/fasthive')
        try:
            link=account['beehivelinked']
        except:
            link=False
        if link == False:
            return render_template('notlincked.html')
        id=account['bhid']
        logins=database()
        founddata=logins.find_one({id:{ '$exists' : True }})
        if founddata:
            if 'password' in session and 'username' in session:
                session.pop('username',None)
                session.pop('password',None)
            leaderbo=leaderboarddb()
            behave=(leaderbo.find_one({'top_behaviour_points': {'$exists': True}}))
            reward=(leaderbo.find_one({'top_reward_points': {'$exists': True}}))
            users = logins.count_documents({})
            timetable=founddata[id]['timetable']

            now = datetime.now()
            current_day = now.strftime('%A')
            current_time = now.time()

            sorted_events = sorted(founddata[id]['noticeboard'], key=lambda x: datetime.strptime(x['time'], '%Y-%m-%dT%H:%M:%S'), reverse=True)
            assighments=founddata[id]['assighments']
            sorted_assignments = dict(sorted(
                assighments.items(),
                key=lambda x: datetime.strptime(x[1]['deadline'], '%Y-%m-%dT%H:%M:%S')
            ))
            for assignment in sorted_assignments.values():
                assignment['deadline'] = assignment['deadline'].split('T')[0]
            def parse_time(time_str):
                if len(time_str) == 5:
                    return datetime.strptime(time_str, '%H:%M').time()
                elif len(time_str) == 8:
                    return datetime.strptime(time_str, '%H:%M:%S').time()

            def get_next_lesson(schedule, current_day, current_time):
                if current_day in schedule:
                    day_schedule = schedule[current_day]
                    for lesson_id, lesson in day_schedule.items():
                        lesson_times = lesson['times'].split(' to ')
                        start_time = parse_time(lesson_times[0])
                        end_time = parse_time(lesson_times[1])
                        
                        if current_time < start_time:
                            return f"Next lesson: {lesson['subject']} with {lesson['teacher']} in room {lesson['room']} from {lesson['times']}."
                        
                return "Next lesson: No more lessons for today!"

            next_lesson = get_next_lesson(timetable, current_day, current_time)

            

            return render_template('newmain.html',lesson_details=next_lesson,transactions=founddata[id]['transactions'],noticeboard=sorted_events,events=founddata[id]['events'],links=founddata[id]['links'],users=users,behave=behave,reward=reward,Attendance=founddata[id]['attendance'],Absences=founddata[id]['absences'],Lates=founddata[id]['lates'],Behaviour=founddata[id]['behaviourPoints'],Reward=founddata[id]['rewardPoints'],name=founddata[id]['name'],form=founddata[id]['tutorGroup'],balance=founddata[id]['balance'],print=founddata[id]['printbalance'],data=sorted_assignments,timetable=timetable)
    return render_template('info.html')


@app.route('/updating')
def updating():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
            return redirect('/login')
        try:
            link=account['beehivelinked']
        except:
            link=False
        if link == False:
            return render_template('notlincked.html')
        id=account['bhid']
        task_statuses[id] = False
        return render_template('updating.html', task_id=id)
    else:
        return redirect('/')

@app.route('/start_task', methods=['POST'])
def start_task():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
            return redirect('/login')
        try:
            link=account['beehivelinked']
        except:
            link=False
        if link == False:
            return render_template('notlincked.html')
        id=account['bhid']
        token=account['bhtoken']
        if 'username' in session and 'password' in session:
            threading.Thread(target=fetchall(token,id,session['username'],session['password'])).start()
            return jsonify({'status': 'started'})
        else:
            threading.Thread(target=fetchall(token,id,None,None)).start()
            return jsonify({'status': 'started'})
 

@app.route('/task_status/<task_id>')
def task_status_route(task_id):
    status = task_statuses.get(task_id, False)
    return jsonify({'complete': status}) 

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html")

@app.route('/logout')
def logout():
    session.pop('userid', None)
    return redirect('/') 

@app.route('/whiteboard')
@cache.memoize(timeout=60)
def whiteboard():
    return render_template('whiteboard.html')

@app.route('/save', methods=['POST'])
def save():
    data = request.json.get('data')
    board = Whiteboard.query.first()

    if board:
        board.data = data
    else:
        board = Whiteboard(data=data)
        whiteboarddb.session.add(board)
    whiteboarddb.session.commit()
    return jsonify(success=True)

@app.route('/load', methods=['GET'])
def load():
    board = Whiteboard.query.first()
    if board:
        return jsonify(success=True, data=board.data)
    return jsonify(success=False)

@app.route('/privacy')
@cache.memoize(timeout=60)
def privacy():
    return render_template('privacy.html')

@app.route('/tos')
@cache.memoize(timeout=60)
def tos():
    return render_template('tos.html')

@app.route('/forums')
@cache.memoize(timeout=60)
def forums_page():
    forumsdb = forums()
    questions = forumsdb.find().sort('timestamp', -1)
    if 'userid' in session:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        return render_template('forums.html', questions=questions, user=account)
    return render_template('forums.html', questions=questions)

@app.route('/forums/ask', methods=['POST'])
def ask_question():
    if 'userid' not in session:
        return redirect('/login')
    
    title = request.form.get('title')
    content = request.form.get('content')
    logged_accounts = accounts()
    account = logged_accounts.find_one({'userid': session['userid']})
    
    question = {
        'title': title,
        'content': content,
        'author': account['username'],
        'timestamp': datetime.now(),
        'answers': [],
        'question_id': str(uuid.uuid4())
    }
    
    forumsdb = forums()
    forumsdb.insert_one(question)
    return redirect('/forums')

@app.route('/forums/answer/<question_id>', methods=['POST'])
def post_answer(question_id):
    if 'userid' not in session:
        return redirect('/login')
    
    answer_content = request.form.get('answer')
    logged_accounts = accounts()
    account = logged_accounts.find_one({'userid': session['userid']})
    
    answer = {
        'content': answer_content,
        'author': account['username'],
        'timestamp': datetime.now()
    }
    
    forumsdb = forums()
    forumsdb.update_one(
        {'question_id': question_id},
        {'$push': {'answers': answer}}
    )
    return redirect('/forums')

@app.route('/portfolio')
@cache.memoize(timeout=600)
def portfolio():
    return render_template('portfolio.html')


@app.route('/cloudstorage')
@cache.memoize(timeout=60)
def cloudstorage():
    if 'userid' in session:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if account == None:
            session.pop('userid', None)
            return redirect('/login?next=/cloudstorage')
            
        try:
            with open('files/headerfile.json', 'r') as f:
                file_data = json.load(f)
        except:
            file_data = {}
            
        username = account['username']
        user_files = []
        
        for file_id, file_info in file_data.items():
            if file_info['owner'] == username:
                user_files.append({
                    'id': file_id,
                    'name': file_info['name'],
                    'shared': file_info['shared']
                })
                
        return render_template('cloudstorage.html', files=user_files)
        
    return redirect('/login?next=/cloudstorage')


@app.route('/cloudstorage/upload', methods=['POST'])
def upload_file():
    if 'userid' not in session:
        return redirect('/login')
        
    if 'file' not in request.files:
        return redirect('/cloudstorage')
        
    file = request.files['file']
    if file.filename == '':
        return redirect('/cloudstorage')
        
    logged_accounts = accounts()
    account = logged_accounts.find_one({'userid': session['userid']})
    username = account['username']
    
    file_id = str(uuid.uuid4())
    
    try:
        with open('files/headerfile.json', 'r') as f:
            file_data = json.load(f)
    except:
        file_data = {}
        
    file_data[file_id] = {
        'name': file.filename,
        'owner': username,
        'shared': False
    }
    
    with open('files/headerfile.json', 'w') as f:
        json.dump(file_data, f)
        
    file.save(f'files/{username}/{file.filename}')
    return redirect('/cloudstorage')
    
@app.route('/cloudstorage/share/<id>')
def share_file(id):
    try:
        with open('files/headerfile.json', 'r') as f:
            file_data = json.load(f)
    except:
        return "File not found", 404
        
    if id not in file_data or not file_data[id]['shared']:
        return "File not shared", 403
        
    username = file_data[id]['owner']
    filename = file_data[id]['name']
    
    return send_from_directory(f'files/{username}', filename, as_attachment=True)


@app.route('/cloudstorage/changesharemode/<id>')
def change_share_mode(id):
    if 'userid' not in session:
        return redirect('/login')
        
    try:
        with open('files/headerfile.json', 'r') as f:
            file_data = json.load(f)
    except:
        return redirect('/cloudstorage')
        
    if id in file_data:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if file_data[id]['owner'] == account['username']:
            file_data[id]['shared'] = not file_data[id]['shared']
            
            with open('files/headerfile.json', 'w') as f:
                json.dump(file_data, f)
                
    return redirect('/cloudstorage')


@app.route('/cloudstorage/delete/<id>')
def delete_file(id):
    if 'userid' not in session:
        return redirect('/login')
        
    try:
        with open('files/headerfile.json', 'r') as f:
            file_data = json.load(f)
    except:
        return redirect('/cloudstorage')
        
    if id in file_data:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if file_data[id]['owner'] == account['username']:
            os.remove(f"files/{account['username']}/{file_data[id]['name']}")
            del file_data[id]
            with open('files/headerfile.json', 'w') as f:
                json.dump(file_data, f)
                
    return redirect('/cloudstorage')



@app.route('/createboard', methods=["POST"])
def createboard():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        else:
            if request.method == 'POST':
                try:
                    name = request.form.get('name')
                    description = request.form.get('description')
                    if name == "" or description == "":
                        return redirect('/home')
                    data=boards()           
                    if data.find_one({"name":name}) == None:
                        data.insert_one({"name":name, "description":description, "owner":account['userid'], "members":[]})
                    else:
                        return redirect('/home')
                except:
                    pass

                return redirect('/home')
    return redirect('/login')

@app.route('/createmessage', methods=["POST"])
def createmessage():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        else:
            if request.method == 'POST':
                try:
                    content = request.form.get('content')
                    boardname = request.form.get('boardname')
                    print(content)
                    print(boardname)

                    if content == "" or boardname == "":
                        return redirect('/home')
                    data=messages()
                    data.insert_one({"board":boardname, "content":content, "owner":account['userid'], "messageid":str(uuid.uuid4()), "date":datetime.now(), "upvotes":0, "downvotes":0, "comments":[]})
                except:
                    pass

                return redirect('/home')
    return redirect('/login')


@app.route('/updown', methods=["POST"])
def updown():
    if 'userid' in session:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if account is None:
            return jsonify({'success': False, 'error': 'Not logged in'})
        
        data = request.get_json()
        direction = data.get('direction')
        message_chain = data.get('messageChain')
        
        if not direction or not message_chain:
            return jsonify({'success': False, 'error': 'Invalid data'})
            
        message_data = messages()
        current_message = message_data.find_one({'messageid': message_chain[0]})
        
        target = current_message
        for i in range(1, len(message_chain)):
            for comment in target['comments']:
                if comment['messageid'] == message_chain[i]:
                    target = comment
                    break
        
        author = logged_accounts.find_one({'userid': target['owner']})
        user_id = account['userid']
        score_change = 0
        voted = False
        
        if 'voted_by' not in target:
            target['voted_by'] = {'up': [], 'down': []}
        
        if direction == 'up':
            if user_id in target['voted_by']['up']:
                target['voted_by']['up'].remove(user_id)
                target['upvotes'] -= 1
                score_change = -1
                voted = False
            else:
                if user_id in target['voted_by']['down']:
                    target['voted_by']['down'].remove(user_id)
                    target['downvotes'] -= 1
                    score_change += 1
                target['voted_by']['up'].append(user_id)
                target['upvotes'] += 1
                score_change += 1
                voted = True
                
        elif direction == 'down':
            if user_id in target['voted_by']['down']:
                target['voted_by']['down'].remove(user_id)
                target['downvotes'] -= 1
                score_change = 1
                voted = False
            else:
                if user_id in target['voted_by']['up']:
                    target['voted_by']['up'].remove(user_id)
                    target['upvotes'] -= 1
                    score_change -= 1
                target['voted_by']['down'].append(user_id)
                target['downvotes'] += 1
                score_change -= 1
                voted = True
        
        message_data.replace_one({'messageid': message_chain[0]}, current_message)
        
        if author and score_change != 0:
            if 'score' not in author:
                author['score'] = 0
            author['score'] += score_change
            logged_accounts.replace_one({'userid': author['userid']}, author)
        
        return jsonify({
            'success': True,
            'upvotes': target['upvotes'],
            'downvotes': target['downvotes'],
            'voted': voted,
            'author_score': author['score']
        })
            
    return jsonify({'success': False, 'error': 'Not logged in'})


@app.route('/home')
def home():
    board_data = boards()
    message_data = messages()
    logged_accounts = accounts()
    
    all_boards = list(board_data.find())
    
    today = datetime.now() - timedelta(days=1)
    top_posts = list(message_data.find({
        'date': {'$gte': today}
    }).sort([
        ('upvotes', -1),
        ('downvotes', 1)
    ]).limit(10))

    for message in top_posts:
        author = logged_accounts.find_one({'userid': message['owner']})
        message['author_name'] = author['username']
        message['author_score'] = author.get('score', 0)
        message['content'] = message['content']

    if 'userid' in session:
        account = logged_accounts.find_one({'userid':session['userid']})
        if account is None:
            session.pop('userid', None)
            return render_template('home.html', 
                                loggedin=False,
                                messages=top_posts,
                                boards=all_boards,
                                not_user_boards=[])

        user_boards = list(board_data.find({'$or': [
            {'owner': account['userid']},
            {'members': account['userid']}
        ]}))

        not_user_boards = list(board_data.find({'$nor': [
            {'owner': account['userid']},
            {'members': account['userid']}
        ]}))

        return render_template('home.html', 
                             loggedin=True,
                             boards=user_boards,
                             not_user_boards=not_user_boards, 
                             messages=top_posts,
                             username=account['username'])

    return render_template('home.html',
                         loggedin=False,
                         messages=top_posts,
                         boards=[],
                         not_user_boards=all_boards)




@app.route('/board/<board_id>')
def board(board_id):
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        else:
            return render_template('board.html', loggedin=True)
    return render_template('board.html')

@app.route('/board/<boardName>/details', methods=['GET'])
def board_details(boardName):
    board_data = boards()
    board = board_data.find_one({'name': boardName})
    if board:
        board['_id'] = str(board['_id'])
        return jsonify({
            'name': board.get('name'),
            'description': board.get('description'),
            'owner': board.get('owner'),
            'members': board.get('members', [])
        })
    else:
        return jsonify({'error': 'Board not found'}), 404

@app.route('/board/<boardName>/messages', methods=['GET'])
def board_messages(boardName):
    message_data = messages()
    logged_accounts = accounts()  
    msgs = list(message_data.find({'board': boardName}))
    output = []
    for msg in msgs:
        if isinstance(msg.get('date'), datetime):
            msg['date'] = msg['date'].isoformat()
        author = logged_accounts.find_one({'userid': msg['owner']})
        msg['author_name'] = author['username'] if author else 'Unknown'
        msg['author_score'] = author.get('score', 0) if author else 0
        msg['_id'] = str(msg['_id'])
        output.append(msg)
    return jsonify(output)

@app.route('/board/<boardName>/join', methods=['POST'])
def join_board(boardName):
    if 'userid' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'}), 401

    user_id = session['userid']
    board_data = boards()
    board = board_data.find_one({'name': boardName})
    if not board:
        return jsonify({'success': False, 'error': 'Board not found'}), 404

    if user_id == board.get('owner'):
         return jsonify({'success': True, 'message': 'You own this board'})
    elif user_id in board.get('members', []):
         return jsonify({'success': True, 'message': 'You are already a member'})
    board_data.update_one({'name': boardName}, {'$push': {'members': user_id}})
    return jsonify({'success': True, 'message': 'You are now a member'})


@app.route('/post/<messageid>')
def post(messageid):
    if 'userid' in session:
        logged_accounts = accounts()
        account = logged_accounts.find_one({'userid': session['userid']})
        if account is None:
            session.pop('userid', None)
            return redirect('/login')
        
        message_data = messages()
        post = message_data.find_one({'messageid': messageid})
        
        if post:
            author = logged_accounts.find_one({'userid': post['owner']})
            post['author_name'] = author['username']
            post['author_score'] = author.get('score', 0)
            return render_template('post.html', 
                                loggedin=True, 
                                message=post,
                                username=account['username'])
    
    return redirect('/login')

@app.route('/replies/<messageid>')
def get_replies(messageid):
    message_data = messages()
    parent_chain = request.args.get('chain', '').split(',')
    message = message_data.find_one({'messageid': parent_chain[0]})
    
    if message:
        current = message
        for chain_id in parent_chain[1:]:
            for comment in current['comments']:
                if comment['messageid'] == chain_id:
                    current = comment
                    break
        
        logged_accounts = accounts()
        replies = []
        
        if 'comments' in current:
            for reply in current['comments']:
                author = logged_accounts.find_one({'userid': reply['owner']})
                reply['author_name'] = author['username']
                reply['author_score'] = author.get('score', 0)
                replies.append(reply)
                
        return jsonify(replies)
    return jsonify([])


@app.route('/reply', methods=['POST'])
def add_reply():
    if 'userid' not in session:
        return jsonify({'success': False, 'error': 'Not logged in'})
        
    data = request.get_json()
    parent_id = data.get('parent_id')
    content = data.get('content')
    parent_chain = data.get('parent_chain', [])

    
    message_data = messages()
    logged_accounts = accounts()
    account = logged_accounts.find_one({'userid': session['userid']})
    
    reply = {
        'messageid': str(uuid.uuid4()),
        'content': content,
        'owner': account['userid'],
        'date': datetime.now(),
        'upvotes': 0,
        'downvotes': 0,
        'comments': [],
        'voted_by': {'up': [], 'down': []}
    }
    
    message = message_data.find_one({'messageid': parent_chain[0]})
    current = message
    for chain_id in parent_chain[1:]:
        for comment in current['comments']:
            if comment['messageid'] == chain_id:
                current = comment
                break
    current['comments'].append(reply)
    
    result = message_data.replace_one({'messageid': parent_chain[0]}, message)
    
    reply['author_name'] = account['username']
    reply['author_score'] = account.get('score', 0)
    
    return jsonify({'success': True, 'reply': reply})

with app.app_context():
    whiteboarddb.create_all()

if __name__ == '__main__':
    app.run(host='0.0.0.0')