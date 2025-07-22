from  datetime import datetime

def get_current_day():
    today = datetime.today().strftime('%A')
    if today == 'Sunday':
        return 'Monday'
    return today