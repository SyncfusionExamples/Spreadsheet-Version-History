# Python Server

This Python server provides real-time collaborative editing and Version History support for the Syncfusion Spreadsheet sample.

## Prerequisites

- Python 3.
- .NET 10 SDK
- Redis connection
- Valid Syncfusion license key

## Build the .NET Wrapper

Navigate to the wrapper project:

```powershell
cd NETStandardWrapperLibrary\WebServiceLibrary
```

Build and publish the wrapper:

```powershell
dotnet restore
dotnet build -c Release
dotnet publish -c Release
```

Return to the Python server folder:

```powershell
cd ..\..\..
```

## Install Python Dependencies

Install the required packages:

```powershell
python -m pip install -r requirements.txt
```

## Configure Redis

Update the Redis settings in `appsettings.json`:

```json
{
  "Redis": {
    "Host": "YOUR_REDIS_HOST",
    "Port": 6380,
    "Password": "YOUR_REDIS_ACCESS_KEY",
    "Ssl": true,
    "AbortConnect": false
  }
}
```

Do not commit actual Redis credentials.

## Configure the Syncfusion License

Open app.py and add the Syncfusion license key as the default value in the following line:

```powershell
LICENSE_KEY = os.environ.get("SYNCFUSION_LICENSE_KEY","YOUR_SYNCFUSION_LICENSE_KEY").strip()
```

Do not commit the license key to the repository.

## Run the Server

```powershell
python app.py
```

The server starts at:

```text
http://127.0.0.1:5000/
```

## Run the Vue Client

Set the service URL in `client/vue/src/App.vue`:

```ts
const serviceUrl: string = 'http://127.0.0.1:5000/';
```

Then run:

```powershell
cd client\vue
npm install
npm run dev
```

Open the URL displayed in the terminal. Use the same room URL in multiple browser windows to test collaborative editing and Version History.
