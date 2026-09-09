- [API](https://ampache.org/api/)
- API JSON Methods

On this page

# Ampache API — JSON Methods

> Source: https://ampache.org/api/api-json-methods  
> Examples directory: `examples/` (raw JSON responses from ampache/python3-ampache, api8 branch)  
> Converted: 2026-09-03


## API JSON Methods[​](#api-json-methods "Direct link to API JSON Methods")

Let's go through come calls and examples that you can do for each JSON method.

Parameters may be sent as a query string, or (for `POST`/`PUT`/`PATCH`/`DELETE`) as a form-encoded or `application/json` request body. See [API](https://ampache.org/api/#news) for details.

Valid responses will always return a HTTP 200 response.

Error responses return codes based on the error type:

- HTTP 400
  - Error '4710': BAD_REQUEST
  - Error '4705': MISSING
- HTTP 401
  - Error '4701': INVALID_HANDSHAKE
- HTTP 403
  - Error '4700': ACCESS_CONTROL_NOT_ENABLED
  - Error '4703': ACCESS_DENIED
  - Error '4742': FAILED_ACCESS_CHECK
- HTTP 404
  - Error '4704': NOT_FOUND
- HTTP 410
  - Error '4706': DEPRECATED
- HTTP 500
  - Error '4702': GENERIC_ERROR

Binary data methods will not return JSON; just the file/data you have requested.

Binary methods will also return:

- HTTP 400 responses for a bad or incomplete request
- HTTP 404 responses where the requests data was not found
- HTTP 416 responses where the stream is unable to return the requested content-range

For information about about how playback works and what a client can expect from Ampache check out [API Media Methods](https://ampache.org/api/api-media-methods)

## Auth Methods[​](#auth-methods "Direct link to Auth Methods")

Auth methods are used for authenticating or checking the status of your session in an Ampache server.

Remember that the auth parameter does not need to be sent as a parameter in the URL.

[HTTP header authentication](https://ampache.org/api/#http-header-authentication) is supported for the auth parameter where present.

### artist[​](#artist "Direct link to artist")

This returns a single artist based on the UID of said artist

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | UID of Artist, returns artist JSON | NO |
| 'include' | string | `albums`, `songs` (include child objects in the response) | YES |

- return object

Returns a single object.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| name | string | YES | NO |  |
| prefix | string | YES | NO |  |
| basename | string | YES | NO |  |
| albums | array\<[AlbumObject](#album)\> | NO | NO | see [AlbumObject](#album) fields |
| albumcount | integer | NO | NO |  |
| songs | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |
| songcount | integer | NO | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| mbid | string | YES | NO |  |
| summary | string | YES | NO |  |
| time | integer | NO | NO |  |
| yearformed | integer | NO | NO |  |
| placeformed | string | YES | NO |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/artist.json)

### artist_albums[​](#artist_albums "Direct link to artist_albums")

This returns the albums of an artist

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | UID of Artist, returns Album JSON | NO |
| 'album_artist' | boolean | `0`, `1` (if true filter for album artists only) | YES |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results to return | YES |
| 'cond' | string | Apply additional filters to the browse using `;` separated comma string pairs | YES |
|  |  | (e.g. 'filter1,value1;filter2,value2') |  |
| 'sort' | string | Sort name or comma-separated key pair. (e.g. 'name,order') | YES |
|  |  | Default order 'ASC' (e.g. 'name,ASC' == 'name') |  |

- return array

Returns a `album` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| album | array\<[AlbumObject](#album)\> | NO | NO | see [AlbumObject](#album) fields |

Each `album` entry ([AlbumObject](#album)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| name | string | YES | NO |  |
| prefix | string | YES | NO |  |
| basename | string | YES | NO |  |
| artist | object | YES | YES | `{id, name, prefix, basename}` |
| artists | array\<[NamedReference](#namedreference)\> | NO | YES | see [NamedReference](#namedreference) fields |
| songartists | array\<[NamedReference](#namedreference)\> | NO | YES | see [NamedReference](#namedreference) fields |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| tracks | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |
| songcount | integer | NO | NO |  |
| diskcount | integer | NO | NO |  |
| type | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| mbid | string | YES | NO |  |
| mbid_group | string | YES | NO |  |
| catalog | string | NO | NO |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/artist_albums.json)

### songs[​](#songs "Direct link to songs")

Returns songs based on the specified filter

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | Filter results to match this string | YES |
| 'exact' | boolean | `0`, `1` (if true filter is exact `=` rather than fuzzy `LIKE`) | YES |
| 'add' | set_filter | ISO 8601 Date Format (2020-09-16) Find objects with an 'add' date newer than the specified date | YES |
| 'update' | set_filter | ISO 8601 Date Format (2020-09-16) Find objects with an 'update' time newer than the specified date | YES |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results to return | YES |
| 'cond' | string | Apply additional filters to the browse using `;` separated comma string pairs | YES |
|  |  | (e.g. 'filter1,value1;filter2,value2') |  |
| 'sort' | string | Sort name or comma-separated key pair. (e.g. 'name,order') | YES |
|  |  | Default order 'ASC' (e.g. 'name,ASC' == 'name') |  |

- return array

Returns a `song` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| song | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |

Each `song` entry ([SongObject](#song)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| title | string | YES | NO |  |
| name | string | YES | NO |  |
| artist | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| artists | array\<[NamedReference](#namedreference)\> | NO | NO | see [NamedReference](#namedreference) fields |
| album | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| albumartist | [NamedReference](#namedreference) | NO | YES | see [NamedReference](#namedreference) fields |
| disk | integer | NO | NO |  |
| disksubtitle | string | YES | NO |  |
| bpm | number | YES | NO |  |
| track | integer | NO | NO |  |
| filename | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| mood | array\<object\> | NO | NO | `{id, name}` |
| playlisttrack | integer | NO | NO |  |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| format | string | YES | NO |  |
| stream_format | string | YES | NO |  |
| bitrate | integer | YES | NO |  |
| stream_bitrate | integer | YES | NO |  |
| rate | integer | NO | NO |  |
| mode | string | YES | NO |  |
| mime | string | YES | NO |  |
| stream_mime | string | YES | NO |  |
| url | string | NO | NO |  |
| size | integer | NO | NO |  |
| mbid | string | YES | NO |  |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| playcount | integer | NO | NO |  |
| last_played | string | YES | NO |  |
| catalog | string | NO | NO |  |
| composer | string | YES | NO |  |
| channels | integer | YES | NO |  |
| comment | string | YES | NO |  |
| license | string | YES | NO |  |
| publisher | string | YES | NO |  |
| language | string | YES | NO |  |
| lyrics | string | YES | NO |  |
| replaygain_album_gain | number | YES | NO |  |
| replaygain_album_peak | number | YES | NO |  |
| replaygain_track_gain | number | YES | NO |  |
| replaygain_track_peak | number | YES | NO |  |
| r128_album_gain | number | YES | NO |  |
| r128_track_gain | number | YES | NO |  |
| metadata | object\<string, string\> | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/songs.json)

### song[​](#song "Direct link to song")

returns a single song

| Input    | Type   | Description                    | Optional |
|----------|--------|--------------------------------|---------:|
| 'filter' | string | UID of Song, returns song JSON |       NO |

- return object

Returns a single object.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| title | string | YES | NO |  |
| name | string | YES | NO |  |
| artist | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| artists | array\<[NamedReference](#namedreference)\> | NO | NO | see [NamedReference](#namedreference) fields |
| album | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| albumartist | [NamedReference](#namedreference) | NO | YES | see [NamedReference](#namedreference) fields |
| disk | integer | NO | NO |  |
| disksubtitle | string | YES | NO |  |
| bpm | number | YES | NO |  |
| track | integer | NO | NO |  |
| filename | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| mood | array\<object\> | NO | NO | `{id, name}` |
| playlisttrack | integer | NO | NO |  |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| format | string | YES | NO |  |
| stream_format | string | YES | NO |  |
| bitrate | integer | YES | NO |  |
| stream_bitrate | integer | YES | NO |  |
| rate | integer | NO | NO |  |
| mode | string | YES | NO |  |
| mime | string | YES | NO |  |
| stream_mime | string | YES | NO |  |
| url | string | NO | NO |  |
| size | integer | NO | NO |  |
| mbid | string | YES | NO |  |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| playcount | integer | NO | NO |  |
| last_played | string | YES | NO |  |
| catalog | string | NO | NO |  |
| composer | string | YES | NO |  |
| channels | integer | YES | NO |  |
| comment | string | YES | NO |  |
| license | string | YES | NO |  |
| publisher | string | YES | NO |  |
| language | string | YES | NO |  |
| lyrics | string | YES | NO |  |
| replaygain_album_gain | number | YES | NO |  |
| replaygain_album_peak | number | YES | NO |  |
| replaygain_track_gain | number | YES | NO |  |
| replaygain_track_peak | number | YES | NO |  |
| r128_album_gain | number | YES | NO |  |
| r128_track_gain | number | YES | NO |  |
| metadata | object\<string, string\> | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/song.json)

### albums[​](#albums "Direct link to albums")

This returns albums based on the provided search filters

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | Filter results to match this string | YES |
| 'include' | string | `albums`, `songs` (include child objects in the response) | YES |
| 'exact' | boolean | `0`, `1` (if true filter is exact `=` rather than fuzzy `LIKE`) | YES |
| 'add' | set_filter | ISO 8601 Date Format (2020-09-16) Find objects with an 'add' date newer than the specified date | YES |
| 'update' | set_filter | ISO 8601 Date Format (2020-09-16) Find objects with an 'update' time newer than the specified date | YES |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results to return | YES |
| 'cond' | string | Apply additional filters to the browse using `;` separated comma string pairs | YES |
|  |  | (e.g. 'filter1,value1;filter2,value2') |  |
| 'sort' | string | Sort name or comma-separated key pair. (e.g. 'name,order') | YES |
|  |  | Default order 'ASC' (e.g. 'name,ASC' == 'name') |  |

- return array

Returns a `album` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| album | array\<[AlbumObject](#album)\> | NO | NO | see [AlbumObject](#album) fields |

Each `album` entry ([AlbumObject](#album)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| name | string | YES | NO |  |
| prefix | string | YES | NO |  |
| basename | string | YES | NO |  |
| artist | object | YES | YES | `{id, name, prefix, basename}` |
| artists | array\<[NamedReference](#namedreference)\> | NO | YES | see [NamedReference](#namedreference) fields |
| songartists | array\<[NamedReference](#namedreference)\> | NO | YES | see [NamedReference](#namedreference) fields |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| tracks | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |
| songcount | integer | NO | NO |  |
| diskcount | integer | NO | NO |  |
| type | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| mbid | string | YES | NO |  |
| mbid_group | string | YES | NO |  |
| catalog | string | NO | NO |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/albums.json)

### album[​](#album "Direct link to album")

This returns a single album based on the UID provided

| Input     | Type   | Description                                     | Optional |
|-----------|--------|-------------------------------------------------|---------:|
| 'filter'  | string | UID of Album, returns album JSON                |       NO |
| 'include' | string | `songs` (include child objects in the response) |      YES |

- return object

Returns a single object.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| name | string | YES | NO |  |
| prefix | string | YES | NO |  |
| basename | string | YES | NO |  |
| artist | object | YES | YES | `{id, name, prefix, basename}` |
| artists | array\<[NamedReference](#namedreference)\> | NO | YES | see [NamedReference](#namedreference) fields |
| songartists | array\<[NamedReference](#namedreference)\> | NO | YES | see [NamedReference](#namedreference) fields |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| tracks | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |
| songcount | integer | NO | NO |  |
| diskcount | integer | NO | NO |  |
| type | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| mbid | string | YES | NO |  |
| mbid_group | string | YES | NO |  |
| catalog | string | NO | NO |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/album.json)

### album_songs[​](#album_songs "Direct link to album_songs")

This returns the songs of a specified album

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | UID of Album, returns song JSON | NO |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results to return | YES |
| 'cond' | string | Apply additional filters to the browse using `;` separated | YES |
|  |  | comma string pairs (e.g. 'filter1,value1;filter2,value2') |  |
| 'sort' | string | Sort name or comma-separated key pair. (e.g. 'name,order') | YES |
|  |  | Default order 'ASC' (e.g. 'name,ASC' == 'name') |  |

- return array

Returns a `song` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| song | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |

Each `song` entry ([SongObject](#song)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| title | string | YES | NO |  |
| name | string | YES | NO |  |
| artist | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| artists | array\<[NamedReference](#namedreference)\> | NO | NO | see [NamedReference](#namedreference) fields |
| album | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| albumartist | [NamedReference](#namedreference) | NO | YES | see [NamedReference](#namedreference) fields |
| disk | integer | NO | NO |  |
| disksubtitle | string | YES | NO |  |
| bpm | number | YES | NO |  |
| track | integer | NO | NO |  |
| filename | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| mood | array\<object\> | NO | NO | `{id, name}` |
| playlisttrack | integer | NO | NO |  |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| format | string | YES | NO |  |
| stream_format | string | YES | NO |  |
| bitrate | integer | YES | NO |  |
| stream_bitrate | integer | YES | NO |  |
| rate | integer | NO | NO |  |
| mode | string | YES | NO |  |
| mime | string | YES | NO |  |
| stream_mime | string | YES | NO |  |
| url | string | NO | NO |  |
| size | integer | NO | NO |  |
| mbid | string | YES | NO |  |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| playcount | integer | NO | NO |  |
| last_played | string | YES | NO |  |
| catalog | string | NO | NO |  |
| composer | string | YES | NO |  |
| channels | integer | YES | NO |  |
| comment | string | YES | NO |  |
| license | string | YES | NO |  |
| publisher | string | YES | NO |  |
| language | string | YES | NO |  |
| lyrics | string | YES | NO |  |
| replaygain_album_gain | number | YES | NO |  |
| replaygain_album_peak | number | YES | NO |  |
| replaygain_track_gain | number | YES | NO |  |
| replaygain_track_peak | number | YES | NO |  |
| r128_album_gain | number | YES | NO |  |
| r128_track_gain | number | YES | NO |  |
| metadata | object\<string, string\> | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/album_songs.json)

### artist_songs[​](#artist_songs "Direct link to artist_songs")

This returns the songs of the specified artist

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | UID of Artist, returns Song JSON | NO |
| 'top50' | boolean | `0`, `1` (if true filter to the artist top 50) | YES |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results to return | YES |
| 'cond' | string | Apply additional filters to the browse using `;` separated comma string pairs | YES |
|  |  | (e.g. 'filter1,value1;filter2,value2') |  |
| 'sort' | string | Sort name or comma-separated key pair. (e.g. 'name,order') | YES |
|  |  | Default order 'ASC' (e.g. 'name,ASC' == 'name') |  |

- return array

Returns a `song` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| song | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |

Each `song` entry ([SongObject](#song)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| title | string | YES | NO |  |
| name | string | YES | NO |  |
| artist | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| artists | array\<[NamedReference](#namedreference)\> | NO | NO | see [NamedReference](#namedreference) fields |
| album | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| albumartist | [NamedReference](#namedreference) | NO | YES | see [NamedReference](#namedreference) fields |
| disk | integer | NO | NO |  |
| disksubtitle | string | YES | NO |  |
| bpm | number | YES | NO |  |
| track | integer | NO | NO |  |
| filename | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| mood | array\<object\> | NO | NO | `{id, name}` |
| playlisttrack | integer | NO | NO |  |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| format | string | YES | NO |  |
| stream_format | string | YES | NO |  |
| bitrate | integer | YES | NO |  |
| stream_bitrate | integer | YES | NO |  |
| rate | integer | NO | NO |  |
| mode | string | YES | NO |  |
| mime | string | YES | NO |  |
| stream_mime | string | YES | NO |  |
| url | string | NO | NO |  |
| size | integer | NO | NO |  |
| mbid | string | YES | NO |  |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| playcount | integer | NO | NO |  |
| last_played | string | YES | NO |  |
| catalog | string | NO | NO |  |
| composer | string | YES | NO |  |
| channels | integer | YES | NO |  |
| comment | string | YES | NO |  |
| license | string | YES | NO |  |
| publisher | string | YES | NO |  |
| language | string | YES | NO |  |
| lyrics | string | YES | NO |  |
| replaygain_album_gain | number | YES | NO |  |
| replaygain_album_peak | number | YES | NO |  |
| replaygain_track_gain | number | YES | NO |  |
| replaygain_track_peak | number | YES | NO |  |
| r128_album_gain | number | YES | NO |  |
| r128_track_gain | number | YES | NO |  |
| metadata | object\<string, string\> | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/artist_songs.json)

### stats[​](#stats "Direct link to stats")

Get some items based on some simple search types and filters. (Random by default) This method **HAD** partial backwards compatibility with older api versions but it has now been removed Pass -1 limit to get all results. (0 will fall back to the `popular_threshold` value)

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'type' | string | `song`, `album`, `artist`, `video`, `playlist`, `podcast`, `podcast_episode` | NO |
| 'filter' | string | `newest`, `highest`, `frequent`, `recent`, `forgotten`, `flagged`, `random` | YES |
| 'user_id' | integer |  | YES |
| 'username' | string |  | YES |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results (Use `popular_threshold` when missing; default 10) | YES |

- return array

Returns a `video` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| video | array\<[VideoObject](#video)\> | NO | NO | see [VideoObject](#video) fields |

Each `video` entry ([VideoObject](#video)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| title | string | YES | NO |  |
| mime | string | YES | NO |  |
| resolution | string | YES | NO |  |
| size | integer | NO | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| time | integer | NO | NO |  |
| url | string | NO | NO |  |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| playcount | integer | NO | NO |  |
| last_played | string | YES | NO |  |
| catalog | string | NO | NO |  |

- throws object

``` prism-code
"error": ""
```

SONG [Example](examples/stats_song.json)

ARTIST [Example](examples/stats_artist.json)

ALBUM [Example](examples/stats_album.json)

### playlists[​](#playlists "Direct link to playlists")

This returns playlists based on the specified filter

| Input | Type | Description | Optional |
|----|----|----|---:|
| 'filter' | string | Filter results to match this string | YES |
| 'hide_search' | integer | `0`, `1` (if true do not include searches/smartlists in the result) | YES |
| 'show_dupes' | integer | `0`, `1` (if true if true ignore 'api_hide_dupe_searches' setting) | YES |
| 'exact' | boolean | `0`, `1` (if true filter is exact `=` rather than fuzzy `LIKE`) | YES |
| 'add' | set_filter | ISO 8601 Date Format (2020-09-16) Find objects with an 'add' date newer than the specified date | YES |
| 'update' | set_filter | ISO 8601 Date Format (2020-09-16) Find objects with an 'update' time newer than the specified date | YES |
| 'offset' | integer | Return results starting from this index position | YES |
| 'limit' | integer | Maximum number of results to return | YES |
| 'cond' | string | Apply additional filters to the browse using `;` separated comma string pairs | YES |
|  |  | (e.g. 'filter1,value1;filter2,value2') |  |
| 'sort' | string | Sort name or comma-separated key pair. (e.g. 'name,order') | YES |
|  |  | Default order 'ASC' (e.g. 'name,ASC' == 'name') |  |

- return array

Returns a `playlist` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| playlist | array\<[PlaylistObject](#playlist)\> | NO | NO | see [PlaylistObject](#playlist) fields |

Each `playlist` entry ([PlaylistObject](#playlist)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| name | string | YES | NO |  |
| owner | string | YES | NO |  |
| user | [UserSummaryObject](#users) | NO | NO | see [UserSummaryObject](#users) fields |
| items | array\<object\> \| integer | NO | NO |  |
| type | string | YES | NO |  |
| art | string | YES | NO |  |
| has_access | boolean | NO | NO |  |
| has_collaborate | boolean | NO | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| md5 | string | YES | NO |  |
| last_update | integer | YES | NO |  |
| time | integer | NO | NO |  |
| playlist_folder_id | string | NO | YES |  |
| playlist_folder_sort_order | integer | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/playlists.json)

### playlist[​](#playlist "Direct link to playlist")

This returns a single playlist

| Input    | Type   | Description                            | Optional |
|----------|--------|----------------------------------------|---------:|
| 'filter' | string | UID of playlist, returns playlist JSON |       NO |

- return object

Returns a single object.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| name | string | YES | NO |  |
| owner | string | YES | NO |  |
| user | [UserSummaryObject](#users) | NO | NO | see [UserSummaryObject](#users) fields |
| items | array\<object\> \| integer | NO | NO |  |
| type | string | YES | NO |  |
| art | string | YES | NO |  |
| has_access | boolean | NO | NO |  |
| has_collaborate | boolean | NO | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| md5 | string | YES | NO |  |
| last_update | integer | YES | NO |  |
| time | integer | NO | NO |  |
| playlist_folder_id | string | NO | YES |  |
| playlist_folder_sort_order | integer | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/playlist.json)

### playlist_songs[​](#playlist_songs "Direct link to playlist_songs")

This returns the songs for a playlist

| Input    | Type    | Description                                      | Optional |
|----------|---------|--------------------------------------------------|---------:|
| 'filter' | string  | UID of Playlist, returns song JSON               |       NO |
| 'random' | integer | `0`, `1` (if true get random songs using limit)  |      YES |
| 'offset' | integer | Return results starting from this index position |      YES |
| 'limit'  | integer | Maximum number of results to return              |      YES |

- return array

Returns a `song` list.

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| total_count | integer | NO | NO |  |
| md5 | string | NO | NO |  |
| song | array\<[SongObject](#song)\> | NO | NO | see [SongObject](#song) fields |

Each `song` entry ([SongObject](#song)):

| Field | Type | Nullable | Optional | Notes |
|----|----|:--:|:--:|----|
| id | string | NO | NO |  |
| title | string | YES | NO |  |
| name | string | YES | NO |  |
| artist | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| artists | array\<[NamedReference](#namedreference)\> | NO | NO | see [NamedReference](#namedreference) fields |
| album | [NamedReference](#namedreference) | NO | NO | see [NamedReference](#namedreference) fields |
| albumartist | [NamedReference](#namedreference) | NO | YES | see [NamedReference](#namedreference) fields |
| disk | integer | NO | NO |  |
| disksubtitle | string | YES | NO |  |
| bpm | number | YES | NO |  |
| track | integer | NO | NO |  |
| filename | string | YES | NO |  |
| genre | array\<[GenreReference](#genrereference)\> | NO | NO | see [GenreReference](#genrereference) fields |
| mood | array\<object\> | NO | NO | `{id, name}` |
| playlisttrack | integer | NO | NO |  |
| time | integer | NO | NO |  |
| year | integer | NO | NO |  |
| format | string | YES | NO |  |
| stream_format | string | YES | NO |  |
| bitrate | integer | YES | NO |  |
| stream_bitrate | integer | YES | NO |  |
| rate | integer | NO | NO |  |
| mode | string | YES | NO |  |
| mime | string | YES | NO |  |
| stream_mime | string | YES | NO |  |
| url | string | NO | NO |  |
| size | integer | NO | NO |  |
| mbid | string | YES | NO |  |
| art | string | YES | NO |  |
| has_art | boolean | NO | NO |  |
| flag | boolean | NO | NO |  |
| rating | integer | YES | NO |  |
| averagerating | number | YES | NO |  |
| playcount | integer | NO | NO |  |
| last_played | string | YES | NO |  |
| catalog | string | NO | NO |  |
| composer | string | YES | NO |  |
| channels | integer | YES | NO |  |
| comment | string | YES | NO |  |
| license | string | YES | NO |  |
| publisher | string | YES | NO |  |
| language | string | YES | NO |  |
| lyrics | string | YES | NO |  |
| replaygain_album_gain | number | YES | NO |  |
| replaygain_album_peak | number | YES | NO |  |
| replaygain_track_gain | number | YES | NO |  |
| replaygain_track_peak | number | YES | NO |  |
| r128_album_gain | number | YES | NO |  |
| r128_track_gain | number | YES | NO |  |
| metadata | object\<string, string\> | NO | YES |  |

- throws object

``` prism-code
"error": ""
```

[Example](examples/playlist_songs.json)

### goodbye[​](#goodbye "Direct link to goodbye")

Destroy a session using the auth parameter.

| Input  | Type   | Description                                    | Optional |
|--------|--------|------------------------------------------------|---------:|
| 'auth' | string | (Session ID) destroys the session if it exists |       NO |

- return object

``` prism-code
"success": ""
```

- throws object

``` prism-code
"error": ""
```

[Example](examples/goodbye.json)

