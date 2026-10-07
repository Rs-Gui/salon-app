import os
import time

# A agenda usa datetime.now() (hora local). Em servidores Linux (Vercel, em UTC)
# fixa o fuso do salão; no Windows tzset não existe e vale o fuso da máquina.
if hasattr(time, "tzset"):
    os.environ["TZ"] = os.environ.get("SALAO_TZ", "America/Sao_Paulo")
    time.tzset()
