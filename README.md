


virtual in vs code:
py -m venv .venv
.\.venv\Scripts\activate

git init     
git remote add origin https://github.com/RedMac9/db_test.git
git switch -c main   

git add .
git commit -m "Your descriptive commit message"
git push origin main

git clone https://github.com/RedMac9/FinRep2.git
git switch -c Changes2025Q1

.\.venv\Scripts\activate.bat
.\.venv\Scripts\Activate.ps1

pip install -r requirements.txt

google authentication Service Account (Konto Usługi)  https://cloud.google.com/iam/docs/service-accounts-create

python .\app\main.py

python app\old_fix\FULL_MARKETS_MACD_GPWv2.py

pip install yfinance --upgrade --no-cache-dir

 VPS: kamil321
        login: root

       serwer: kamil321.mikrus.xyz
     port SSH: 10321 (to ważne!)
   adres IPv6: 2a01:4f9:3b:50c1::321
       serwer: srv36 (tutaj fizycznie znajduje się Twój VPS)

on server:

systemctl status cron
crontab -e
10 20 * * * cd /root/FinSup2 && venv/bin/python3 app/main.py >> logs/log.txt 2>&1


python app/main.py
pip install -r requirements.txt

python app/main.py

python3 -m venv venv
source venv/bin/activate

npm install -g npm@11.4.2   
npm install -g @google/gemini-cli

##### GEMINI install

in vs code terminal: npm install -g @google/gemini-cli

npx @google/gemini-cli

###### GEMINI uninstal 
Here are the steps to completely remove Gemini CLI from your Windows system:
Step 1: Uninstall the package using npm

    Open your command prompt (CMD) or PowerShell.

    Run the following command to uninstall the global package:

    bash
    npm uninstall -g @google/gemini-cli

This command tells npm to remove (uninstall) the global (-g) package named @google/gemini-cli from your system.
Step 2: (Optional but recommended) Clean up configuration files

The uninstaller might leave behind the configuration folder and the environment variable. To fully clean up, you should remove them manually.

    Delete the configuration folder:
    Navigate to your user directory and delete the .gemini folder. You can do this by running the following command in your terminal:

bash
rmdir /s /q "C:\Users\%USERNAME%\.gemini"

This will remove the settings.json file and any other configuration you might have created.