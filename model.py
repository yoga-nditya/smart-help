import pyodbc
import json
from datetime import datetime

def get_connection():
    return pyodbc.connect(
        "DRIVER={ODBC Driver 17 for SQL Server};"
        "SERVER=10.141.1.165;DATABASE=master;UID=dbadmin;PWD=Password*1!"
    )

def get_user(clientid,secretekey):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"""select top 1 * from [UserDB].[dbo].[ClientIDMap]   
                where ClientID = '{clientid}'
                and ClientSecret = '{secretekey}' """
        cursor.execute(sql)
        record = cursor.fetchone()
        
        if record:
            if len(record) > 0:
                columns = [desc[0] for desc in cursor.description]
                record_dict = dict(zip(columns, record))

                # Konversi datetime ke string
                for key, value in record_dict.items():
                    if isinstance(value, datetime):
                        record_dict[key] = value.isoformat()  # atau str(value)

                hasil = json.dumps(record_dict, indent=2,)
                return hasil
            else:
                return False
        else:
            return False
    except Exception as e:
        print(e)
        return False
    
def get_user_key(clientid):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"""select ClientSecret from [UserDB].[dbo].[ClientIDMap]   
                where ClientID = '{clientid}'"""
        cursor.execute(sql)
        record = cursor.fetchone()
        
        if record:
            if len(record) > 0:
                print(record[0])
                return record[0]
            else:
                return False
        else:
            return False
    except Exception as e:
        print(e)
        return False
def get_ready(status):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"""SELECT top 1 [ChatUserId]
            ,[UserRoleId]
            ,[ChatTypeId]
            ,[ChatStatusId]
            ,[ReadyOn]
            ,[Status]
            ,[ModifiedOn]
            ,[ModifiedBy]
            ,[CreatedOn]
            ,[CreatedBy]
        FROM [TenantProDB].[dbo].[ChatUser]
        where ChatStatusId = {status} 
        order by ReadyOn asc"""
        cursor.execute(sql)
        record = cursor.fetchone()
        if record:
            if len(record) > 0:
                columns = [desc[0] for desc in cursor.description]
                record_dict = dict(zip(columns, record))

                # Konversi datetime ke string
                for key, value in record_dict.items():
                    if isinstance(value, datetime):
                        record_dict[key] = value.isoformat()  # atau str(value)

                hasil = json.dumps(record_dict, indent=2,)
                return hasil
        else:
            return False
    except:
        return False
    
def update_chatuser(roileid,status):
    try:
        conn = get_connection()
        cursor = conn.cursor()
        sql = f"""UPDATE [TenantProDB].[dbo].[ChatUser]
        SET ChatStatusId = {status}, ReadyOn = GETDATE(),ModifiedOn = GETDATE(), ModifiedBy = 'System'
        WHERE UserRoleId = {roileid}"""
        cursor.execute(sql)
        print(sql)
        conn.commit()
        return True
    except Exception as e:
        print(e)
        return False