#!/usr/bin/env python3
#Import Flask Library
from flask import Flask, render_template, request, session, url_for, redirect
import pymysql.cursors
import os

#Initialize the app from Flask
app = Flask(__name__)

#Configure MySQL
conn = pymysql.connect(host='127.0.0.1',
                       port = 3306,
                       user='root',
                       password='',
                       db='finnstagram',
                       charset='utf8mb4',
                       cursorclass=pymysql.cursors.DictCursor)

#Define a route to hello function
@app.route('/')
def hello():
    return render_template('index.html')

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, password))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for('home'))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

#Authenticates the register
@app.route('/registerAuth', methods=['GET', 'POST'])
def registerAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']

    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s'
    cursor.execute(query, (username))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    error = None
    if(data):
        #If the previous query returns data, then user exists
        error = "This user already exists"
        return render_template('register.html', error = error)
    else:
        ins = 'INSERT INTO Person VALUES(%s, %s, NULL, NULL, NULL, NULL, NULL)'
        cursor.execute(ins, (username, password))
        conn.commit()
        cursor.close()
        return render_template('index.html')


@app.route('/home')
def home():
    user = session['username']
    #selecting posts
    cursor = conn.cursor();
    query = "SELECT Photo.photoID,photoOwner,Timestamp,filePath,caption FROM Photo JOIN Share JOIN CloseFriendGroup JOIN Belong WHERE username = '" + user + "' OR Belong.groupOwner = '" + user + "' UNION (SELECT photoID, photoOwner, Timestamp, filePath, caption FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = '" + user + "' and acceptedFollow= 1) UNION (SELECT Photo.photoID,photoOwner,Timestamp,filePath,caption FROM Photo WHERE photoOwner = '" + user + "') ORDER BY Timestamp DESC;"
    cursor.execute(query)
    data = cursor.fetchall()
    #selecting tags
    query = "SELECT q.photoID, fname, lname FROM (SELECT Photo.photoID FROM Photo JOIN Share JOIN CloseFriendGroup JOIN Belong WHERE Belong.username = '" + user + "' OR Belong.groupOwner = '" + user + "') as q JOIN Tag JOIN Person ON q.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1 UNION (SELECT t.photoID, fname, lname FROM (SELECT Photo.photoID FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = '" + user + "' and acceptedFollow = 1) as t JOIN Tag JOIN Person ON t.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1) UNION (SELECT v.photoID, fname, lname FROM (SELECT Photo.photoID FROM Photo WHERE photoOwner = '" + user + "') as v JOIN Tag JOIN Person ON v.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1);"
    cursor.execute(query)
    tags = cursor.fetchall()
    # query that puts the Photos that are Share(d) to a CloseFriendGroup that user belongs to
    query = "SELECT groupName FROM belong WHERE username = '" +user + "' OR groupOwner = '" + user + "';"
    cursor.execute(query)
    closegroups = cursor.fetchall()
    cursor.close()
    return render_template('home.html', username=user, posts=data, tagged=tags, groups=closegroups)

@app.route('/post', methods=['GET', 'POST'])
def post():
    username = session['username']
    cursor = conn.cursor();
    filepath = request.form['filepath']
    caption = request.form['caption']
    #allFollowers
    if request.form.get('visible'):
        visible = '1'
    else:
        visible = '0'
    #inserting photo into table
    query = 'INSERT INTO Photo (photoOwner, filePath, caption, allFollowers) VALUES(%s, %s, %s, %s )'
    cursor.execute(query, (username, filepath, caption, visible))
    conn.commit()
    cursor.close()
    #sharing w showGroups
    #loop going through all avaliable groups
    cursor = conn.cursor();
    i = 1;
    while request.form.get(str(i)):
        #getting groupName
        group = request.form.get(str(i))
        #getting groupOwner
        query = "SELECT groupOwner from belong where groupName = '" + group + "' and username = '" + username + "' or groupOwner = '" + username + "';"
        cursor.execute(query)
        owner = cursor.fetchall()
        #getting photoID
        query = "SELECT photoID FROM Photo where photoOwner = '" + username + "' ORDER BY photoID DESC LIMIT 1;"
        cursor.execute(query)
        id = cursor.fetchall()
        #inserting into Share
        query = "INSERT INTO share VALUES(%s,%s,%s)"
        cursor.execute(query, (str(group),str(owner[0]['groupOwner']), id[0]['photoID']))
        i += 1
    conn.commit()
    cursor.close()
    return redirect(url_for('home'))

@app.route('/select_blogger')
def select_blogger():
    #check that user is logged in
    #username = session['username']
    #should throw exception if username not found

    cursor = conn.cursor();
    query = 'SELECT DISTINCT photoOwner FROM Photo'
    cursor.execute(query)
    data = cursor.fetchall()
    cursor.close()
    return render_template('select_blogger.html', user_list=data)

@app.route('/show_posts', methods=["GET", "POST"])
def show_posts():
    poster = request.args['poster']
    cursor = conn.cursor();
    query = 'SELECT Timestamp, photoID FROM Photo ORDER BY Timestamp DESC'
    cursor.execute(query, poster)
    data = cursor.fetchall()
    cursor.close()
    return render_template('show_posts.html', poster_name=poster, posts=data)

@app.route('/logout')
def logout():
    session.pop('username')
    return redirect('/')

# deleting cache so the styles update
@app.context_processor
def override_url_for():
    return dict(url_for=dated_url_for)

def dated_url_for(endpoint, **values):
    if endpoint == 'static':
        filename = values.get('filename', None)
        if filename:
            file_path = os.path.join(app.root_path,
                                 endpoint, filename)
            values['q'] = int(os.stat(file_path).st_mtime)
    return url_for(endpoint, **values)

app.secret_key = 'some key that you will never guess'
#Run the app on localhost port 5000
#debug = True -> you don't have to restart flask
#for changes to go through, TURN OFF FOR PRODUCTION
if __name__ == "__main__":
    app.run('127.0.0.1', 5000, debug = True)
