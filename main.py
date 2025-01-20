from flask import Flask, render_template, request, redirect, session, jsonify
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


# Load config.yaml
with open('config.yaml') as f:
    config = yaml.load(f, Loader=SafeLoader)

task_statuses = {}

# Flask app setup

app = Flask(__name__, static_folder='static')
app.secret_key = 'your_secret_key'
app.jinja_env.globals.update(zip=zip)

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

To complete your account setup, please click the verification link below:
{ymaldata['website']}/verify/{code}

or visit {ymaldata['website']}/verify
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
        printbalance=(response.json()[0]['printCreditBalance'])
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
        print('done')
        databasedb=database()
        print('test')
        find=databasedb.find_one({str(id): {'$exists': True}})
        print(find)
        if find == None or find == '':
            try:  
                print('db1')
                print(databasedb.insert_one({
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
                        }))
                print('db2')
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
    if 'token' in session and 'id' in session:
        logins=database()
        found=logins.find_one({session['id']: { '$exists' : True } })
        if found:
            data=submit_assighment(session['token'],session['id'],ass)
            print(data)
            if data == True:
                result = logins.update_one(
                    {session['id']: {'$exists': True}},
                    {"$set": {f"{session['id']}.assighments.{ass}.completed": True}}
                )
                print(result)
        
        return redirect('/fasthive/')
    return redirect('/fasthive/login')

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


# Schedule the rescan job to run every hour

scheduler = BackgroundScheduler()
scheduler.add_job(
    func=rescan,
    trigger=IntervalTrigger(hours=1.5),
    id='rescan_job',
    name='Rescan database every hour',
    replace_existing=True
)
scheduler.start()

# Routes

@app.route('/')
def index():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
        else:
            return render_template('index.html', loggedin=True)
    return render_template('index.html')

@app.route('/store')
def store():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
    return render_template('store.html', products=config['products'])

@app.route('/vapedetectors')
def vapedetectorspage():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
    
    return render_template('vapedetectors.html')

@app.route('/fasthiveinfo')
def fasthiveinfo():
    if 'userid' in session:
        logged_accounts=accounts()
        account = logged_accounts.find_one({'userid':session['userid']})
        if account == None:
            session.pop('userid', None)
    
    return render_template('info.html')

@app.route('/contact', methods=['GET', 'POST'])
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
            return redirect('/')
        else:
            session.pop('userid', None)
    if request.method == 'POST':
        logged_accounts=accounts()
        email = (request.form['email']).lower()
        password = request.form['password']

        account = logged_accounts.find_one({'email':email})
        if account != None:
            if check_password_hash(account['password'], password):
                session['userid'] = account['userid']

                try:
                    account['beehivelinked']
                    session['token'] = account['bhtoken']
                    session['id'] = account['bhid']
                except:
                    pass
                
                return redirect('/')
            else:
                return render_template('login.html', error='Invalid Password')
        else:
            unaccounts = unverified_accounts()
            if unaccounts.find_one({'email':email}):
                return redirect('/verify')
            return render_template('login.html', error='Invalid Email')

    return render_template('login.html')


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

    return redirect('/login')

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
                    user.send_email(f"""Vape Detected: \nDate: {str((datetime.now()).strftime('%d-%m-%Y'))} \nTime: {str((datetime.now()).strftime('%H:%M'))}\nRoom: {room}""", email, "Vape Detected" , 'plain') 
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
                    user.send_email(f"""Tamper Detected: \nDate: {str((datetime.now()).strftime('%d-%m-%Y'))} \nTime: {str((datetime.now()).strftime('%H:%M'))}\nRoom: {room}""", email, "Vape Detected" , 'plain') 
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
                        user.send_email(f'New VapeDetector adopted: {room}\nThis will be added to the panel.', email, "Device Adopted", 'plain') 
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
                            session['token'] = response[0]
                            session['id'] = response[1]
                            session['username'] = username
                            session['password'] = password
                            account["beehivelinked"] = "True"
                            account["bhtoken"] = response[0]
                            account["bhid"] = response[1]
                            logged_accounts.replace_one({'userid':session['userid']}, account)
                            return redirect('/updating')
                        return render_template('profile.html', error2='Invalid Beehive credentials', link=link)

            return render_template('profile.html',link=link)
    return redirect('/login')





@app.route('/events/<ass>')
def eventss(ass):
    return 'Currently not avalable <a href="/">Home</a> '

@app.route('/fasthive/')
def fasthive():
    if 'token' in session and 'id' in session:
        logins=database()
        founddata=logins.find_one({session['id']:{ '$exists' : True }})
        if founddata:
            if 'password' in session and 'username' in session:
                session.pop('username',None)
                session.pop('password',None)
            leaderbo=leaderboarddb()
            behave=(leaderbo.find_one({'top_behaviour_points': {'$exists': True}}))
            reward=(leaderbo.find_one({'top_reward_points': {'$exists': True}}))
            users = logins.count_documents({})
            timetable=founddata[session['id']]['timetable']

            now = datetime.now()
            current_day = now.strftime('%A')
            current_time = now.time()

            sorted_events = sorted(founddata[session['id']]['noticeboard'], key=lambda x: datetime.strptime(x['time'], '%Y-%m-%dT%H:%M:%S'), reverse=True)
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

            

            return render_template('newmain.html',lesson_details=next_lesson,transactions=founddata[session['id']]['transactions'],noticeboard=sorted_events,events=founddata[session['id']]['events'],links=founddata[session['id']]['links'],users=users,behave=behave,reward=reward,Attendance=founddata[session['id']]['attendance'],Absences=founddata[session['id']]['absences'],Lates=founddata[session['id']]['lates'],Behaviour=founddata[session['id']]['behaviourPoints'],Reward=founddata[session['id']]['rewardPoints'],name=founddata[session['id']]['name'],form=founddata[session['id']]['tutorGroup'],balance=founddata[session['id']]['balance'],print=founddata[session['id']]['printbalance'],data=founddata[session['id']]['assighments'],timetable=timetable)
    return redirect('/profile')


@app.route('/updating')
def updating():
    if 'token' in session and 'id' in session:
        task_statuses[session['id']] = False
        return render_template('updating.html', task_id=session['id'])
    else:
        return redirect('/')

@app.route('/start_task', methods=['POST'])
def start_task():
    if 'token' in session and 'id' in session:
        if 'username' in session and 'password' in session:
            threading.Thread(target=fetchall(session['token'],session['id'],session['username'],session['password'])).start()
            return jsonify({'status': 'started'})
        else:
            threading.Thread(target=fetchall(session['token'],session['id'],None,None)).start()
            return jsonify({'status': 'started'})
 

@app.route('/task_status/<task_id>')
def task_status_route(task_id):
    status = task_statuses.get(task_id, False)
    return jsonify({'complete': status})




@app.route('/startreload', methods=['POST'])
def startreload():
    if 'token' in session and 'id' in session:
        if session['id'] == '7ba6339d-e764-ef11-8154-005056a23846':
            threading.Thread(target=rescan()).start()
            return jsonify({'status': 'started'})
        

@app.errorhandler(404)
def not_found(e):
    return render_template("404.html")

@app.route('/logout')
def logout():
    session.pop('userid', None)
    try:
        session.pop('token', None)
        session.pop('id', None)
    except:
        pass
    return redirect('/') 
if __name__ == '__main__':
    app.run(host='0.0.0.0')