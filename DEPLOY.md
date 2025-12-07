# Xanula Deployment Guide - PythonAnywhere

Deploy Xanula to PythonAnywhere with custom domain `xanula.reepls.com`.

---

## Prerequisites

- PythonAnywhere **paid account** (for custom domains)
- GitHub repository with your code
- Domain DNS access (for xanula.reepls.com)

---

## Part 1: Prepare Your Local Project

### 1.1 Create requirements.txt

```bash
pip freeze > requirements.txt
```

### 1.2 Verify .gitignore includes sensitive files

```
.env
*.pyc
__pycache__/
media/
staticfiles/
*.sqlite3
```

### 1.3 Push latest code to GitHub

```bash
git add .
git commit -m "Prepare for deployment"
git push origin main
```

---

## Part 2: Set Up PythonAnywhere

### 2.1 Create Account & Open Bash Console

1. Go to [pythonanywhere.com](https://www.pythonanywhere.com)
2. Sign up or login (need paid account for custom domain)
3. Go to **Consoles** → **Start a new console** → **Bash**

### 2.2 Clone Your Repository

```bash
cd ~
git clone https://github.com/SaahBrice/xanula-init.git xanula
cd xanula
```

### 2.3 Create Virtual Environment

```bash
python3.12 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install -r requirements.txt
```

> **Note**: Use Python version matching your local version. Check with `python --version`

---

## Part 3: Configure Environment Variables

### 3.1 Create .env file on PythonAnywhere

```bash
nano ~/.env
```

Add your production environment variables:

```env
# Django Settings
DEBUG=False
SECRET_KEY=your-super-secret-production-key-here-make-it-long-and-random
ALLOWED_HOSTS=xanula.reepls.com,yourusername.pythonanywhere.com

# Database (PythonAnywhere MySQL)
DATABASE_URL=mysql://yourusername:yourpassword@yourusername.mysql.pythonanywhere-services.com/yourusername$xanula

# Email Settings (Gmail SMTP example)
EMAIL_HOST=smtp.gmail.com
EMAIL_PORT=587
EMAIL_USE_TLS=True
EMAIL_HOST_USER=your-email@gmail.com
EMAIL_HOST_PASSWORD=your-app-password

# Stripe (Production keys)
STRIPE_PUBLIC_KEY=pk_live_xxxxx
STRIPE_SECRET_KEY=sk_live_xxxxx
STRIPE_WEBHOOK_SECRET=whsec_xxxxx

# Fapshi (if using)
FAPSHI_API_USER=your-api-user
FAPSHI_API_KEY=your-api-key

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Site URL
SITE_URL=https://xanula.reepls.com
```

Press `Ctrl+X`, then `Y`, then `Enter` to save.

### 3.2 Update settings.py to read from ~/.env

In your `xanula_project/settings.py`, the `decouple` library should be able to find the .env file. If not, create a symlink:

```bash
ln -s ~/.env ~/xanula/.env
```

---

## Part 4: Set Up MySQL Database

### 4.1 Create MySQL Database

1. Go to **Databases** tab in PythonAnywhere
2. Create a new database (e.g., `yourusername$xanula`)
3. Note down:
   - Host: `yourusername.mysql.pythonanywhere-services.com`
   - Username: `yourusername`
   - Password: (set one)
   - Database: `yourusername$xanula`

### 4.2 Install MySQL client

```bash
source ~/xanula/venv/bin/activate
pip install mysqlclient
```

### 4.3 Update DATABASE_URL in .env

```env
DATABASE_URL=mysql://yourusername:yourpassword@yourusername.mysql.pythonanywhere-services.com/yourusername$xanula
```

### 4.4 Run Migrations

```bash
cd ~/xanula
source venv/bin/activate
python manage.py migrate
python manage.py createsuperuser
```

---

## Part 5: Collect Static Files

```bash
cd ~/xanula
source venv/bin/activate
python manage.py collectstatic --noinput
```

This creates `staticfiles/` directory with all static assets.

---

## Part 6: Configure Web App

### 6.1 Create Web App

1. Go to **Web** tab in PythonAnywhere
2. Click **Add a new web app**
3. Select **Manual configuration** (NOT Django)
4. Choose **Python 3.12** (match your version)

### 6.2 Configure Virtual Environment

In the **Virtualenv** section, enter:
```
/home/yourusername/xanula/venv
```

### 6.3 Configure WSGI File

Click on the WSGI configuration file link (e.g., `/var/www/yourusername_pythonanywhere_com_wsgi.py`)

**Replace entire contents with:**

```python
import os
import sys
from pathlib import Path

# Add your project directory to the sys.path
project_home = '/home/yourusername/xanula'
if project_home not in sys.path:
    sys.path.insert(0, project_home)

# Load environment variables from ~/.env
from dotenv import load_dotenv
env_path = Path('/home/yourusername/.env')
load_dotenv(dotenv_path=env_path)

# Set Django settings module
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'xanula_project.settings')

# Import Django application
from django.core.wsgi import get_wsgi_application
application = get_wsgi_application()
```

> **Important**: Replace `yourusername` with your actual PythonAnywhere username!

### 6.4 Configure Static Files

In the **Static files** section, add:

| URL | Directory |
|-----|-----------|
| `/static/` | `/home/yourusername/xanula/staticfiles` |
| `/media/` | `/home/yourusername/xanula/media` |

### 6.5 Reload Web App

Click the green **Reload** button.

---

## Part 7: Set Up Custom Domain

### 7.1 Add Domain in PythonAnywhere

1. In **Web** tab, scroll to **Domains** section
2. Click **Add a new domain**
3. Enter: `xanula.reepls.com`

### 7.2 Configure DNS (at your domain registrar)

Add a **CNAME record** for your subdomain:

| Type | Name | Value |
|------|------|-------|
| CNAME | xanula | webapp-xxxxx.pythonanywhere.com |

> The exact CNAME target will be shown in PythonAnywhere after adding the domain.

### 7.3 Enable HTTPS (Free with Let's Encrypt)

1. Wait for DNS propagation (5-30 minutes)
2. In PythonAnywhere **Web** tab, click **Enable HTTPS**
3. It will auto-provision a Let's Encrypt certificate

---

## Part 8: Final Configuration

### 8.1 Update Django Sites Framework

```bash
cd ~/xanula
source venv/bin/activate
python manage.py shell
```

```python
from django.contrib.sites.models import Site
site = Site.objects.get(id=1)
site.domain = 'xanula.reepls.com'
site.name = 'Xanula'
site.save()
exit()
```

### 8.2 Update Stripe Webhook

1. Go to [Stripe Dashboard](https://dashboard.stripe.com/webhooks)
2. Add webhook endpoint: `https://xanula.reepls.com/purchase/webhook/`
3. Select events: `checkout.session.completed`, `payment_intent.succeeded`
4. Copy webhook secret to your `.env` as `STRIPE_WEBHOOK_SECRET`

### 8.3 Update Google OAuth Redirect URI

1. Go to [Google Cloud Console](https://console.cloud.google.com/apis/credentials)
2. Edit your OAuth client
3. Add Authorized redirect URI: `https://xanula.reepls.com/accounts/google/login/callback/`

---

## Part 9: Reload and Test

```bash
# Reload from bash
touch /var/www/yourusername_pythonanywhere_com_wsgi.py
```

Or click **Reload** in the Web tab.

### Test Checklist

- [ ] Homepage loads: `https://xanula.reepls.com`
- [ ] Admin works: `https://xanula.reepls.com/admin/`
- [ ] Static files load (CSS, images)
- [ ] Media files load (book covers)
- [ ] User registration works
- [ ] Google OAuth works
- [ ] Payment flow works (test mode first)
- [ ] Email sending works

---

## Part 10: Ongoing Maintenance

### Pull Updates

```bash
cd ~/xanula
git pull origin main
source venv/bin/activate
pip install -r requirements.txt
python manage.py migrate
python manage.py collectstatic --noinput
touch /var/www/yourusername_pythonanywhere_com_wsgi.py
```

### View Error Logs

```bash
cat /var/log/yourusername.pythonanywhere.com.error.log
```

### Create Scheduled Tasks (for background jobs)

1. Go to **Tasks** tab
2. Add tasks for:
   - Daily reading reminders
   - Payment status checks
   - Cleanup tasks

---

## Troubleshooting

### 500 Server Error
- Check error log: `/var/log/yourusername.pythonanywhere.com.error.log`
- Verify `.env` file exists and is readable
- Ensure all migrations ran

### Static Files Not Loading
- Run `collectstatic` again
- Verify static file mappings in Web tab
- Check file permissions

### Database Connection Error
- Verify MySQL credentials in `.env`
- Check database exists in Databases tab
- Ensure `mysqlclient` is installed

### HTTPS Not Working
- Wait for DNS propagation
- Check CNAME record is correct
- Try enabling HTTPS again after 30 mins

---

## Quick Reference

| Item | Value |
|------|-------|
| **Project Path** | `/home/yourusername/xanula` |
| **Virtualenv** | `/home/yourusername/xanula/venv` |
| **Static Files** | `/home/yourusername/xanula/staticfiles` |
| **Media Files** | `/home/yourusername/xanula/media` |
| **WSGI File** | `/var/www/yourusername_pythonanywhere_com_wsgi.py` |
| **Error Log** | `/var/log/yourusername.pythonanywhere.com.error.log` |
| **Domain** | `xanula.reepls.com` |

---

**🎉 Congratulations! Your Xanula platform is now live at https://xanula.reepls.com**
