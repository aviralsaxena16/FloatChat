import os
from ftplib import FTP

FTP_SERVER = "ftp.ifremer.fr"
ARGO_PATH = "/ifremer/argo/latest_data/"
LOCAL_DOWNLOAD_PATH = "../data/raw_latest/"

def download_latest_data():
    if not os.path.exists(LOCAL_DOWNLOAD_PATH):
        os.makedirs(LOCAL_DOWNLOAD_PATH)

    print(f"Connecting to FTP server: {FTP_SERVER}...")
    # I've kept the timeout from our previous fix, as it's good practice
    with FTP(FTP_SERVER, timeout=30) as ftp:
        try:
            ftp.login()
            print("Login successful.")

            # --- THE FIX: ENABLE PASSIVE MODE ---
            ftp.set_pasv(True)
            print("Passive mode enabled.")
            # ------------------------------------

            ftp.cwd(ARGO_PATH)
            print(f"Checking for latest data in: {ARGO_PATH}")

            latest_files = [f for f in ftp.nlst() if f.endswith('.nc')]
            if not latest_files:
                print("No new NetCDF files found.")
                return

            print(f"Found {len(latest_files)} new files to download.")
            for filename in latest_files:
                local_filepath = os.path.join(LOCAL_DOWNLOAD_PATH, filename)
                print(f"  -> Downloading {filename}")
                with open(local_filepath, 'wb') as f:
                    ftp.retrbinary(f'RETR {filename}', f.write)
        except Exception as e:
            print(f"An error occurred during download: {e}")
    print("\n--- Latest data download complete! ---")

if __name__ == "__main__":
    download_latest_data()