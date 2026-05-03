module.exports = {
  apps: [
    {
      name: 'yaar-backend',
      cwd: '/var/www/yaar-plus/backend',
      script: 'app/main.py',
      interpreter: '/var/www/yaar-plus/backend/.venv/bin/python3',
      instances: 1,
      exec_mode: 'fork',
      autorestart: true,
      watch: false,
      max_memory_restart: '512M',
      env: {
        HOST: '127.0.0.1',
        PORT: '8010',
        DEBUG: 'false',
      },
      error_file: '/var/log/pm2/yaar-backend-error.log',
      out_file: '/var/log/pm2/yaar-backend-out.log',
      merge_logs: true,
      time: true,
    },
  ],
}