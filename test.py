from gofilepy import GofileClient

client = GofileClient()
# client = GofileClient(token="YOUR_TOKEN_HERE")  # Optional token for private uploads
file = client.upload(file=open("./test.py", "rb"))
print(file.name)
print(file.page_link)  # View and download file at this link