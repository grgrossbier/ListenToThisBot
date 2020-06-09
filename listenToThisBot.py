'''
Reads the headlines of the top posts on /r/ListenToThis. Tries to parse those headlines into 
song data, and search for those songs on Spotify. If successful, it will create a playlist of all 
found songs on Spotify, and optionally, post replys to those posts with congratz. 
'''

import praw
import re
import spotipy
import spotipy.util as util
from pprint import pprint
import yaml
import datetime
import time

def load_config(reddit_link, spotify_config_yaml):
    '''
        This function takes in the names and locations of the objects that communicate with reedit and 
        spotify using the 'praw' and 'spotipy' modules. 

        Application accounts need to be segt up with both Reddit and Spotify before you can fun this 
        function and connect with python.

        Parameters
        -------------
        reddit_link: str
            The name of the link in the praw.ini file. Typically located in the working directory. 
            Example praw.ini file:
                [Link-Name]                       # This needs to match reddit_link
                client_id= Client ID
                client_secret= Client Secret
                username= username                 # Not required if you only want to read reddit
                password= password                # Not Required if you only want to read reddit
                user_agent = note, required but not important

        spotify_config_yaml: str
            File name of yaml file with spotify authentication information. Very similar to reddit praw.ini
            but this needs to be a path to the .yaml file. 
            Example of the .yaml file:
                username: 'username'
                client_id: 'clientid'
                client_secret: 'client secret'
                redirect_uri: 'http://www.quarterlifeexcursion.com'

        Returns
        ---------------
        reddit - Class
            instance of the Reddit class used to access the Reddit API
        spotify - Class
            instance of the Spotify class used to access the Spotify API
        spotify_config - dict
            configuration information regarding the spotify login
    '''
    stream = open(spotify_config_yaml)
    spotify_config = yaml.load(stream)
    print('Connecting to Spotify...')  
    token = util.prompt_for_user_token(spotify_config['username'], 
                                   scope='playlist-modify-private,playlist-modify-public', 
                                   client_id=spotify_config['client_id'], 
                                   client_secret=spotify_config['client_secret'], 
                                   redirect_uri=spotify_config['redirect_uri'])
    spotify = spotipy.Spotify(auth=token)
    print('Connecting to Reddit...')
    reddit = praw.Reddit(reddit_link)
    return reddit, spotify, spotify_config

def get_top_songs(subreddit, time_filter='week', score_threshold=60):
    '''
        Gathers the headlines of the top post of a subreddit, based on the parameters, and then tries to parse
        the headlines into Track Title, Artist, Year, and Genre. The ideal post would look like this:

        Black Dog - Led Zeppelin [Classic Rock] (1975)

        It also saves the post's ID number with the song data. 

        Parameters
        -----------------
        subreddit - str
            subreddit of interest -- since it needs to have proper formatting, the only subreddit
            I know of is /r/listentothis

        time_filter - str
            Can be one of: all, day, hour, month, week, year (default: week). 

        score_threshold - int
            Since this is used as a filter, you would typicaly want this value >> 0 in order to filter
            out low karma posts.

        Returns
        -----------------
        track_list - list of dicts
            List of dicts. Each element is {'Track Info':track_info, 'Reddit Post ID':post.id}
            Track info is parsed using parse_reddit_title(). See docs for that. 
    '''
    print('Gathering top songs from Reddit...')
    global reddit
    track_list = []
    for post in reddit.subreddit(subreddit).top(time_filter = time_filter, limit=None):
        if int(post.score) >= score_threshold:
            try:
                track_info = parse_reddit_title(post.title)
                track_list.append({ 'Track Info':track_info, 
                                    'Reddit Post ID':post.id})
            except:
                print("SONG FAILED TO ADD TO LIST")
    print("Song List Generated --- Length = ", len(track_list))            
    return track_list

def inform_post_on_reddit(post_ids, playlist_id, sleep_time):
    '''
        Sends a reply to all the posts that were successfully added to the playlist,
        with a link to the playlist.

        Parameters
        -----------------
        post_ids - list
            list of Reddit post IDs

        playlist_id - str
            playlist id# from spotify

        sleep_time - int
            amount of time in seconds to delay before posting the next reply on reddit. 
            This is to avoid the errors associated with low karma and young accounts posting too much. 

        Returns
        -----------------
        N/A
    '''
    global reddit
    global spotify
    link = spotify.playlist(playlist_id)['external_urls']['spotify']
    message = f'Thanks for posting great music! Beep. Boop! Upvoted and added to a weekly [playlist]({link}).\n\r' + \
                f'This bot parses through the top posts in this subreddit and posts them to a single spotify playlist. Please upvote if you like the way it works, and message me questions or bug reports.'
    print(f'Message -- {message}')
    for i, id_num in enumerate(post_ids):
        print(f'Posting at-a-boys to Reddit... {i+1} of {len(post_ids)}')
        post_object = reddit.submission(id = id_num)
        post_object.upvote()
        post_object.reply(message)
        if i < len(post_ids)-1:
            time.sleep(sleep_time)

def spotify_query(title, artist = None):
    '''
        Search Spotify for a song using API. Used as function by find_song()

        Parameters
        -----------------
        title - str
            song title

        artist - str
            song artist

        Returns
        -----------------
        query['tracks'] - dict
            search result
    '''
    global spotify
    if artist:
        q = 'track:' + title + ' artist:' + artist
    else:
        q = 'track:' + title
    query = spotify.search(q, type = 'track')
    return query['tracks']

def find_song(title, artist):
    '''
        Search spotify for a song. Will return top song found. 

        Attepts to search using both parameters, then using song title and first word of artist, 
        then using only the song title. 

        Accuracy is good, but can be greatly improved. 

        Parameters
        -----------------
        title - str
            song title

        artist - str
            song artist

        Returns
        -----------------
        id_num - str or None
            If found, returns the id of the song accourding to the spotify API. 
    '''
    global spotify
    query = spotify_query(title, artist)
    if query['total'] == 0:
        if ' ' in artist:
            artists = artist.split(' ')
            query = spotify_query(title, artists[0])
        if query['total'] == 0:
            query = spotify_query(title)
    if query['total'] > 0:
        id_num = query['items'][0]['id']
    else:
        id_num = None
    return id_num

def search_spotify_for_ids(track_list):
    '''
        Uses information parsed from reddit titles and stored in a dictionary to search for the 
        exact some song on Spotify. If it succeeds, it adds it to a list, which includes the reddit
        and track information.

        Parameters
        -----------------
        track_list - list of dictionaries
            each list element should be a dictionary with 'Reddit Post ID' and 'Track Info'
            'Track info' should contain another dictionary in it's value that includes Title, Artist,
            Genre, and Year.

        Returns
        -----------------
        found_track_list - list of dictionaries
            same as track_list parameter, but now it only contains the songs that it could find a matching
            'Spotify ID' for, and it adds 'Spotify ID': ###### to the dictionary. 
    '''
    print('Searching for songs on Spotify, fingers crossed...')
    found_track_list = []
    for track in track_list:
        artist = track['Track Info']['Artist']
        title = track['Track Info']['Title']
        print('Searching ... ', title.upper(), ' by ', artist.upper())
        id_num = find_song(title, artist)
        if id_num:
            print('Found! .... Spotify ID: ', id_num)
            found_track_list.append({'Spotify ID': id_num,
                            'Reddit Post ID': track['Reddit Post ID'],
                            'Track Info': track['Track Info']})
    return found_track_list

def create_playlist(playlist_name,track_list=None):
    '''
        Creates a playlist of all the songs identified in 'track_list' parameter.
        It is careful not to create duplicates of songs. 

        Parameters
        -----------------
        playlist_name - str
            name of the new playlist

        Returns
        -----------------
        track_list - list of dictionaries
            each list element should be a dictionary with 'Reddit Post ID', 'Spotify ID', and 'Track Info'
            'Track info' should contain another dictionary in it's value that includes Title, Artist,
            Genre, and Year.
    '''
    print(f'Creating {playlist_name} playlist on Spotify')
    global spotify
    global spotify_config
    username = spotify_config['username']
    current_playlists = spotify.user_playlists(user=username)
    found = False
    for playlist in current_playlists['items']:
        if playlist_name == playlist['name']:
            found = True
    if not found:
        spotify.user_playlist_create(user=username, 
                                    name = playlist_name, 
                                    description = 'A weekly playlist that takes the top songs of the week on /r/ListenToThis and puts them into a single playlist')
    current_playlists = spotify.user_playlists(user=username)
    for playlist in current_playlists['items']:
        if playlist_name == playlist['name']:
            playlist_id = playlist['id']
            break
    current_tracks = spotify.user_playlist_tracks(user=username,
                                                playlist_id = playlist_id)
    for new_song_id in track_list:
        duplicate = False
        for current_track in current_tracks['items']:
            if current_track['track']['id'] == new_song_id['Spotify ID']:
                duplicate = True
        if not duplicate:
            spotify.user_playlist_add_tracks(user=username, 
                                            playlist_id = playlist_id,
                                            tracks = [new_song_id['Spotify ID']])
    return playlist_id

def parse_reddit_title(title):
    '''
        Parses Reddit title into title, artist, year, genre. 

        Required format:  "Black Dog - Led Zeppelin [Classic Rock] (1975)"

        Parameters
        -----------------
        title - str
            post title with the proper format.

        Returns
        -----------------
        track_info - dict
            {'Title': track, 'Artist': artist, 'Genre' : genre, 'Year' : year}
    '''    
    pattern1 = re.compile(r'(\w[^-|^—]+)[-|—|\s]+(\w[^\[^(]+)')
    match = pattern1.findall(title)[0]
    track = match[1].strip()
    artist = match[0].strip()
    try:
        pattern2 = re.compile(r'[\[|\(](\d{4})')
        year = pattern2.findall(title)[0]
    except:
        year = None
    try:
        pattern3 = re.compile(r'[\[|\(](\D+)[\]|\)]')
        genre = pattern3.findall(title)[0]
    except:
        genre = None 
    if len(track) > 75 or len(artist) > 75 or 'discussion' in title.lower():
        track = 'Abort6618031111'
        artist = 'Abort6618031111'
    track_info = {
        'Title': track,
        'Artist': artist,
        'Genre' : genre,
        'Year' : year}
    return track_info
    
def today_YYMMDD():
    '''
        Outputs today's date in a str - "YYMMDD"
    '''
    today = datetime.date.today()
    return today.strftime('%y%m%d')

def run(subreddit = "ListenToThis", time_filter='week', score_threshold=100, post_to_reddit=False):
    '''
        Reads the headlines of the top posts on a specific subreddit. Tries to parse those headlinnes into 
        song data, and search for those songs on Spotify. If successful, it will create a playlist of all 
        found songs on Spotify, and optionally, post replys to those posts with congratz. 

        Parameters
        -----------------
        subreddit - str
            subreddit of interest -- since it needs to have proper formatting, the only subreddit
            I know of is /r/listentothis

        time_filter - str
            Can be one of: all, day, hour, month, week, year (default: week). 

        score_threshold - int
            Since this is used as a filter, you would typicaly want this value >> 0 in order to filter
            out low karma posts.

        post_to_reddit - boolean
            If true, if post replys to Reddit posts. 

        Returns
        -----------------
        N/A
    ''' 
    track_list = get_top_songs(subreddit, time_filter, score_threshold)
    track_list = search_spotify_for_ids(track_list)
    playlist_name = f'/r/{subreddit}_' + today_YYMMDD()
    playlist_id = create_playlist(playlist_name, track_list)
    print('Songs Found = ' , len(track_list))
    print('ID Found = ', len(track_list))
    if post_to_reddit:
        successful_posts = [item['Reddit Post ID'] for item in track_list]
        inform_post_on_reddit(post_ids=successful_posts, playlist_id=playlist_id, sleep_time=60*10)

if __name__ == '__main__':
    global spotify
    global reddit
    global spotify_config
    reddit, spotify, spotify_config = load_config(reddit_link='PlaylistBot-i2000',spotify_config_yaml='spotify_config.yaml')
    run(subreddit = 'ListenToThis', time_filter='week', score_threshold=70, post_to_reddit=True)