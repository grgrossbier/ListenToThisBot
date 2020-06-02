import listenToThisBot as lis
from pprint import pprint

reddit, spotify, spotify_config = lis.load_config(reddit_link='PlaylistBot-i2000',spotify_config_yaml='spotify_config.yaml')

print(reddit.user.me())

pprint(spotify.search(q="black dog",limit=1, type='track')['tracks']['items'][0]['album']['artists'][0]['name'])
