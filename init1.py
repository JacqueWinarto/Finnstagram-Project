#!/usr/bin/env python3
#Import Flask Library
from flask import Flask, render_template, request, session, redirect, url_for, send_file
import os
import uuid
import hashlib
import pymysql.cursors
from functools import wraps
import time

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
    try:
        if session['username']:
            return redirect(url_for("home"))
    except:
        return redirect(url_for("login"))

#Define route for login
@app.route('/login')
def login():
    return render_template('login.html')

#Authenticates the login
@app.route('/loginAuth', methods=['GET', 'POST'])
def loginAuth():
    #grabs information from the forms
    username = request.form['username']
    password = request.form['password']
    hashedPassword = hashlib.sha256(password.encode("utf-8")).hexdigest()
    #cursor used to send queries
    cursor = conn.cursor()
    #executes query
    query = 'SELECT * FROM Person WHERE username = %s and password = %s'
    cursor.execute(query, (username, hashedPassword))
    #stores the results in a variable
    data = cursor.fetchone()
    #use fetchall() if you are expecting more than 1 data row
    cursor.close()
    error = None
    if(data):
        #creates a session for the the user
        #session is a built in
        session['username'] = username
        return redirect(url_for("home"))
    else:
        #returns an error message to the html page
        error = 'Invalid login or username'
        return render_template('login.html', error=error)

#Define route for register
@app.route('/register')
def register():
    return render_template('register.html')

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
        hashedPassword = hashlib.sha256(password.encode("utf-8")).hexdigest()
        ins = 'INSERT INTO Person VALUES(%s, %s, NULL, NULL, NULL, NULL, NULL)'
        cursor.execute(ins, (username, hashedPassword))
        conn.commit()
        cursor.close()
        return render_template('login.html')

@app.route('/home')
@app.route('/home/<error>')
def home(error = None):
    user = session['username']
    #selecting posts
    cursor = conn.cursor();
    query = "SELECT Photo.photoID,photoOwner,Timestamp,filePath,caption FROM Photo NATURAL JOIN Share NATURAL JOIN CloseFriendGroup NATURAL JOIN Belong WHERE username = '" + user + "' OR Belong.groupOwner = '" + user + "' UNION (SELECT photoID, photoOwner, Timestamp, filePath, caption FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = '" + user + "' and acceptedFollow= 1) UNION (SELECT Photo.photoID,photoOwner,Timestamp,filePath,caption FROM Photo WHERE photoOwner = '" + user + "') ORDER BY Timestamp DESC;"
    cursor.execute(query)
    data = cursor.fetchall()
    #selecting tags
    query = "SELECT q.photoID, fname, lname FROM (SELECT Photo.photoID FROM Photo NATURAL JOIN Share NATURAL JOIN CloseFriendGroup NATURAL JOIN Belong WHERE Belong.username = '" + user + "' OR Belong.groupOwner = '" + user + "') as q JOIN Tag JOIN Person ON q.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1 UNION (SELECT t.photoID, fname, lname FROM (SELECT Photo.photoID FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = '" + user + "' and acceptedFollow = 1) as t JOIN Tag JOIN Person ON t.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1) UNION (SELECT v.photoID, fname, lname FROM (SELECT Photo.photoID FROM Photo WHERE photoOwner = '" + user + "') as v JOIN Tag JOIN Person ON v.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1);"
    cursor.execute(query)
    tags = cursor.fetchall()
    # query that puts the shows the close friend groups a person belongs to so they can select them while posting
    query = "SELECT DISTINCT groupName FROM belong WHERE username = '" +user + "' OR groupOwner = '" + user + "';"
    cursor.execute(query)
    closegroups = cursor.fetchall()
    #query that gets all the photos the person has clicked
    #html will handle whether they can like a photo or unlike
    query = "SELECT photoID from liked WHERE username = %s"
    cursor.execute(query,(user))
    liked_posts = cursor.fetchall()
    cursor.close()
    return render_template('home.html', username=user, posts=data, tagged=tags, groups=closegroups, likes = liked_posts, error=error)

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

@app.route('/like', methods=["GET", "POST"])
def like():
    if request.form:
        user = session['username']
        # getting data of the post
        data= request.form.get('like_btn')
        #splitting data into respective variables
        data = data.split(",")
        photo_id = data[0]
        post_id = data[1]
        cursor = conn.cursor()
        query = "INSERT INTO liked(username,photoID) VALUES(%s,%s)"
        try:
            cursor.execute(query, (user,photo_id))
        except pymysql.err.IntegrityError:
            print("Already liked!")
        conn.commit()
        cursor.close()
    # redirect to home, uses posts id in html to go directly to the same post
    return redirect(url_for("home") + "#" + str(post_id))

@app.route('/unlike', methods=["GET", "POST"])
def unlike():
    if request.form:
        user = session['username']
        # getting data of the post
        data= request.form.get('like_btn')
        #splitting data into respective variables
        data = data.split(",")
        photo_id = data[0]
        post_id = data[1]
        cursor = conn.cursor()
        query = "DELETE FROM liked WHERE username = %s AND photoID = %s"
        try:
            cursor.execute(query, (user,photo_id))
        except:
            print("error")
        conn.commit()
        cursor.close()
    # redirect to home, uses posts id in html to go directly to the same post
    return redirect(url_for("home") + "#" + str(post_id))


#Define route for manage_tags page
@app.route('/tags')
@app.route('/tags/<error>')
def tags():
    user = session['username']
    cursor = conn.cursor();
    query = "SELECT tag.photoID, photoOwner, Timestamp, caption, filePath FROM Tag NATURAL JOIN Photo WHERE username = %s AND acceptedTag = 0"
    cursor.execute(query,(user))
    pending_requests = cursor.fetchall()
    cursor.close()
    return render_template('tags.html', requests=pending_requests)

#Add Tag request
@app.route('/addTag', methods=["POST"])
def add_tag():
    if request.form:
        user = session['username']
        photo_id = request.form.get('photo_id')
        added_user = request.form.get('added_user')
        error = False
        cursor = conn.cursor()
        # Check if added_user exists
        query = "SELECT username from Person WHERE username = %s"
        cursor.execute(query,(added_user))
        #if doesn't exist return
        if not cursor.fetchone():
            error = "User does not exist"
        else:
            # Check if added user can see the post
            query = "SELECT Photo.photoID FROM Photo NATURAL JOIN Share NATURAL JOIN CloseFriendGroup NATURAL JOIN Belong WHERE username = %s OR Belong.groupOwner = %s AND Photo.photoID = %s UNION (SELECT photoID FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = %s and acceptedFollow= 1 AND photoID = %s) UNION (SELECT photoID FROM Photo WHERE photoOwner = %s and photoID = %s)"
            cursor.execute(query,(added_user,added_user,photo_id,added_user, photo_id, added_user,photo_id))
            #if not visible
            if not cursor.fetchone():
                error = added_user + " cannot be tagged"
            else:
                #check if tagging themselves
                if added_user == user:
                    query = "INSERT INTO Tag VALUES (%s,%s,1)"
                else:
                    query = "INSERT INTO Tag VALUES (%s,%s,0)"
                try:
                    cursor.execute(query, (added_user, photo_id))
                except pymysql.err.IntegrityError:
                    error = added_user + " is already tagged"
        conn.commit()
        cursor.close()
    else:
        error = "Unknown error, please try again"
    return redirect(url_for('home', error = error))

#updating Tag requests
@app.route('/updateTagRequest', methods=["GET","POST"])
def update_tag_request():
    if request.form:
        user = session['username']
        photoid = request.form.get('id')
        cursor = conn.cursor()
        if request.form["choice"] == "True":
            query = "UPDATE tag SET acceptedTag = 1 WHERE username = %s AND photoID = %s"
        else:
            query = "DELETE FROM tag WHERE username = %s AND photoID = %s"
        cursor.execute(query, (user,photoid))
        conn.commit()
        cursor.close()
        error = None
    else:
        error = "Unknown error, please try again"
    return redirect(url_for("tags")) #loads follow page, probably a better way of doing this

#Define route for manage_follows page
@app.route('/follows')
@app.route('/follows/<error>')
def follows(error = None):
    user = session['username']
    cursor = conn.cursor();
    query = "SELECT followerUsername FROM Follow WHERE followeeUsername = %s AND acceptedfollow = 0"
    cursor.execute(query,(user))
    pending_requests = cursor.fetchall()
    cursor.close()
    return render_template('follows.html', requests=pending_requests, error = error)

#Follow requests
@app.route('/requestFollow', methods=["GET", "POST"])
def request_follow():
    if request.form:
        user = session['username']
        followee = request.form['search'] #user they want to follow
        cursor = conn.cursor()
        # checking if followee exists
        query = 'SELECT username from Person WHERE username = %s'
        cursor.execute(query,(followee))
        requested_followee = cursor.fetchone()
        error = None
        if not requested_followee:
            error = "User does not exist"
        elif followee == user: #trying to follow themself
            error = "Cannot follow yourself"
        else:
            #catch integrity error if already following
            try:
                query = "Insert into Follow VALUES (%s,%s, 0)"
                cursor.execute(query,(user,followee))
                error = False
            except:
                error = "Already sent request!"
        conn.commit()
        cursor.close()
    else:
        error = "Unknown error, please try again"
    return redirect(url_for('follows',error = error)) #loads follow page, probably a better way of doing this but idk

#updating follow requests
@app.route('/updateFollowRequest', methods=["GET","POST"])
def update_follow_request():
    if request.form:
        user = session['username']
        follower = request.form.get('follower')
        cursor = conn.cursor()
        if request.form["choice"] == "True":
            query = "UPDATE follow SET acceptedfollow = 1 WHERE followerUsername = %s AND followeeUsername = %s"
        else:
            query = "DELETE FROM follow WHERE followerUsername = %s AND followeeUsername = %s"
        cursor.execute(query, (follower,user))
        conn.commit()
        cursor.close()
        error = None
    else:
        error = "Unknown error, please try again"
    return redirect(url_for('follows',error = error)) #loads follow page, probably a better way of doing this but idk

#Define route for close friends group page
@app.route('/groups')
def groups(error = None):
    user = session['username']
    cursor = conn.cursor()
    query = "SELECT DISTINCT groupName,groupOwner FROM BELONG WHERE groupOwner = %s or username = %s"
    cursor.execute(query, (user,user))
    close_groups = cursor.fetchall()
    conn.commit()
    cursor.close()
    return render_template("groups.html", groups = close_groups, username = user, error = error)

@app.route('/addGroupMember', methods=["POST"])
def add_group_member():
    if request.form:
        user = session['username']
        group_name = request.form.get('group_name')
        added_user = request.form.get('added_user')
        cursor = conn.cursor()
        # Check if added_user exists
        query = "SELECT username from Person WHERE username = %s"
        cursor.execute(query,(added_user))
        #if doesn't exist return
        if not cursor.fetchone():
            error = "User does not exist"
            return groups(error)
        # Check if user already in groups
        query = "SELECT username from Belong WHERE username = %s and groupName = %s AND groupOwner = %s"
        cursor.execute(query,(added_user, group_name, user))
        #if exist return
        if cursor.fetchone():
            error = added_user + " is already in the group!"
            return groups(error)
        #else
        query = "INSERT INTO Belong VALUES (%s,%s,%s)"
        cursor.execute(query, (group_name, user, added_user))
        conn.commit()
        cursor.close()
        error = False
    else:
        error = "Unknown error, please try again"
    return groups(error) #loads follow page, probably a better way of doing this


# routes for page where you search for users
@app.route('/user')
@app.route('/user/<error>')
def user(error = None):
    return render_template('user.html', error = error)

#route for profile page of users that shows the posts for that user
@app.route('/<selected>')
def show_posts(selected = None):
    user = session['username']
    cursor = conn.cursor();
    query = "SELECT Photo.photoID,photoOwner,Timestamp,filePath,caption FROM Photo NATURAL JOIN Share NATURAL JOIN CloseFriendGroup NATURAL JOIN Belong WHERE (username = %s OR Belong.groupOwner = %s) AND photoOwner = %s UNION (SELECT photoID, photoOwner, Timestamp, filePath, caption FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = %s and acceptedFollow= 1 and photoOwner = %s) ORDER BY Timestamp DESC ;"
    cursor.execute(query, (user,user,selected, user, selected))
    data = cursor.fetchall()
    print(data)
    #selecting tags
    query = 'SELECT q.photoID,Person.username, fname, lname FROM (SELECT Photo.photoID,photo.photoOwner FROM Photo NATURAL JOIN Share NATURAL JOIN CloseFriendGroup NATURAL JOIN Belong WHERE Belong.username = %s OR Belong.groupOwner = %s) as q JOIN Tag JOIN Person ON q.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1 and photoOwner = %s UNION (SELECT t.photoID,Person.username, fname, lname FROM (SELECT Photo.photoID,Photo.photoOwner FROM Photo JOIN Follow ON photoOwner = followeeUsername WHERE followerUsername = %s and acceptedFollow = 1) as t JOIN Tag JOIN Person ON t.photoID = Tag.photoID and Tag.username = Person.username WHERE acceptedTag = 1 and photoOwner = %s)'
    cursor.execute(query, (user,user,selected,user,selected))
    tags = cursor.fetchall()
    query = "SELECT photoID FROM liked WHERE username = %s"
    cursor.execute(query,(user))
    liked_posts = cursor.fetchall()
    return render_template('show_posts.html', username=user, profile = selected, posts=data, tagged=tags, likes= liked_posts)

# route for searching for user, checks if they exist
@app.route('/search_user', methods=["GET", "POST"])
def find_user():
    if request.form:
        user = session['username']
        searched_user = request.form['search'] #user they want to follow
        cursor = conn.cursor()
        # checking if followee exists
        query = 'SELECT username from Person WHERE username = %s'
        cursor.execute(query,(searched_user))
        found_user = cursor.fetchone()
        error = None
        if not found_user:
            error = "User does not exist"
        else:
            conn.commit()
            cursor.close()
            return redirect(url_for('show_posts', selected=found_user['username']))
        conn.commit()
        cursor.close()
        return redirect(url_for('user', error = error))
    else:
        error = "Unknown error, please try again"
    return redirect(url_for('user')) #loads follow page, probably a better way of doing this but idk


#logging out
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
