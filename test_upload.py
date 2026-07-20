import urllib.request
import urllib.parse
import json

boundary = '----WebKitFormBoundary7MA4YWxkTrZu0gW'
body = []

def add_field(name, value):
    body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="{name}"\r\n\r\n{value}\r\n')

add_field('id_modello', '5')
add_field('prompt', 'test')
add_field('temperatura', '0.1')
add_field('max_tokens', '500')
add_field('chunk_size', '1000')

with open('test_reviews.csv', 'rb') as f:
    file_content = f.read().decode('utf-8')

body.append(f'--{boundary}\r\nContent-Disposition: form-data; name="file"; filename="test_reviews.csv"\r\nContent-Type: text/csv\r\n\r\n{file_content}\r\n')
body.append(f'--{boundary}--\r\n')

data = ''.join(body).encode('utf-8')

req = urllib.request.Request("http://localhost:8000/api/upload", data=data)
req.add_header('Content-Type', f'multipart/form-data; boundary={boundary}')

try:
    response = urllib.request.urlopen(req)
    print("Status:", response.status)
    print("Body:", response.read().decode())
except urllib.error.HTTPError as e:
    print("Error Code:", e.code)
    print("Error Body:", e.read().decode())
