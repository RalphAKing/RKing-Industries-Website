import requests

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
    

get_assighments('eyJhbGciOiJodHRwOi8vd3d3LnczLm9yZy8yMDAxLzA0L3htbGRzaWctbW9yZSNobWFjLXNoYTI1NiIsInR5cCI6IkpXVCJ9.eyJodHRwOi8vc2NoZW1hcy54bWxzb2FwLm9yZy93cy8yMDA1LzA1L2lkZW50aXR5L2NsYWltcy9uYW1lIjoiMjAxOWVib3dkZW5AYmVhdWNoYW1wLm9yZy51ayIsImlkIjoiM2RhNjMzOWQtZTc2NC1lZjExLTgxNTQtMDA1MDU2YTIzODQ2IiwibmJmIjoxNzM3MzY0ODYxLCJleHAiOjE3Njg5MDQ4NjEsImlzcyI6Imh0dHBzOi8vYmVlaGl2ZWFwaS5saW9uaGVhcnR0cnVzdC5vcmcudWsiLCJhdWQiOiI0MTRlMTkyN2EzODg0ZjY4YWJjNzlmNzI4MzgzN2ZkMSJ9.NeJzIuzZ1msUFgYkuvri-JXYLj5jgeHlboVZ-z4Trys', '3da6339d-e764-ef11-8154-005056a23846')