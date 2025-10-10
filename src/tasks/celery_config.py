# Celery Configuration for Telegram AI Scraper

# Broker settings
broker_url = 'redis://localhost:6379/0'  # Use Redis as message broker
result_backend = 'redis://localhost:6379/0'

# Task routing - different queues for different types of work
task_routes = {
    'src.tasks.telegram_celery_tasks.process_telegram_message': {'queue': 'telegram_processing'},
    'src.tasks.telegram_celery_tasks.fetch_new_messages_from_all_channels': {'queue': 'telegram_fetch'},
    'src.tasks.telegram_celery_tasks.send_teams_notification': {'queue': 'notifications'},
    'src.tasks.telegram_celery_tasks.save_to_sharepoint': {'queue': 'sharepoint'},
    'src.tasks.telegram_celery_tasks.save_to_csv_backup': {'queue': 'backup'},
    'src.tasks.telegram_celery_tasks.cleanup_old_tasks': {'queue': 'maintenance'},
    'src.tasks.telegram_celery_tasks.health_check': {'queue': 'monitoring'}
}

# Worker configuration - Optimized for t3.small (2GB RAM)
worker_concurrency = 1  # Reduced for memory efficiency
worker_prefetch_multiplier = 1  # Only prefetch one task at a time
task_acks_late = True  # Acknowledge task only after completion
worker_max_tasks_per_child = 100  # Restart worker after 100 tasks (more frequent memory cleanup)

# Retry configuration
task_reject_on_worker_lost = True
task_serializer = 'json'
accept_content = ['json']
result_serializer = 'json'
timezone = 'Asia/Manila'

# Result backend settings
result_expires = 1800  # Results expire after 30 minutes (save memory)

# Task execution settings
task_always_eager = False  # Set to True for testing (runs tasks synchronously)
task_eager_propagates = False
task_ignore_result = False

# Error handling
task_annotations = {
    '*': {
        'rate_limit': '100/m',  # Limit to 100 tasks per minute per worker
        'time_limit': 300,      # Hard time limit: 5 minutes
        'soft_time_limit': 240, # Soft time limit: 4 minutes
    },
    'src.tasks.telegram_celery_tasks.process_telegram_message': {
        'rate_limit': '50/m',   # AI processing is slower
        'time_limit': 180,      # 3 minutes for AI analysis
        'soft_time_limit': 150,
    },
    'src.tasks.telegram_celery_tasks.fetch_new_messages_from_all_channels': {
        'rate_limit': '20/h',   # Max 20 times per hour (every 3 minutes)
        'time_limit': 600,      # 10 minutes for fetching from all channels
        'soft_time_limit': 540,
    },
    'src.tasks.telegram_celery_tasks.send_teams_notification': {
        'rate_limit': '200/m',  # Notifications can be faster
        'time_limit': 30,       # 30 seconds should be enough
        'soft_time_limit': 25,
    },
    'src.tasks.telegram_celery_tasks.save_to_sharepoint': {
        'rate_limit': '30/m',   # SharePoint API has limits
        'time_limit': 120,      # 2 minutes for SharePoint operations
        'soft_time_limit': 100,
    }
}

# Monitoring and logging
worker_send_task_events = True
task_send_sent_event = True
task_track_started = True

# Security
task_reject_on_worker_lost = True
worker_disable_rate_limits = False

# Beat scheduler settings (for periodic tasks)
beat_schedule_filename = '../../logs/celerybeat-schedule'

# Redis connection settings
broker_connection_retry_on_startup = True
broker_connection_retry = True
broker_connection_max_retries = 10

# Result backend settings
result_backend_transport_options = {
    'master_name': 'mymaster',
    'visibility_timeout': 3600,
}

# Pool settings
worker_pool = 'prefork'  # Use process-based pool
worker_pool_restarts = True

# Memory and resource management
worker_max_memory_per_child = 200000  # 200MB per child process
worker_autoscaler = 'celery.worker.autoscale:Autoscaler'

# Logging
worker_log_format = '[%(asctime)s: %(levelname)s/%(processName)s] %(message)s'
worker_task_log_format = '[%(asctime)s: %(levelname)s/%(processName)s][%(task_name)s(%(task_id)s)] %(message)s'

# Queue-specific settings
task_default_queue = 'telegram_processing'
task_default_exchange = 'telegram_scraper'
task_default_exchange_type = 'direct'
task_default_routing_key = 'telegram_processing'

# Queue definitions
task_queues = {
    'telegram_processing': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'telegram_processing',
    },
    'telegram_fetch': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'telegram_fetch',
    },
    'notifications': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'notifications',
    },
    'sharepoint': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'sharepoint',
    },
    'backup': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'backup',
    },
    'maintenance': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'maintenance',
    },
    'monitoring': {
        'exchange': 'telegram_scraper',
        'exchange_type': 'direct',
        'routing_key': 'monitoring',
    }
}