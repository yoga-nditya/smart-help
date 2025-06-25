INSTALL :
- clone terlebih dahulu
- pip install -r requirment.txt

RUN TANPA SSL (PAKAI INI KALAU RUN DI MSI KARNA UDH SSL DI SERVER) :
python -m uvicorn main:app --host 0.0.0.0 --port 8000 --reload

RUN JIKA PAKAI SSL :
python -m uvicorn main:app --host 0.0.0.0 --port 443 --ssl-keyfile ssl/private.key --ssl-certfile ssl/cert.pem --reload