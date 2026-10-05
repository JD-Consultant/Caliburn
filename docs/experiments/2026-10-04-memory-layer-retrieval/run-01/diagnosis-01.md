# 測試資料庫接線診斷與修訂

原 capture.py 在讀 Docker POSTGRES_PASSWORD 設定時失敗：既有容器不提供該設定，且不提供 PASSWORD_FILE；無 schema 或模型呼叫。唯讀無密碼連線也未成功，不推測或修改既有認證。保留原腳本、輸入 manifest 與 console。

修訂 capture-02.py 改用本輪新建的專用容器 caliburn-rag-memory-pg-20261004，loopback 55442、PostgreSQL 18.6、隨機密碼；專用 _test DB 與隨機 schema。密碼只從該容器設定讀入記憶體，不寫實驗檔／模型輸入。原協定記載的既有 55437 容器未用於寫入，所有既有資料不變。這是環境修訂，不改八案、角色、模型、切分或評分。新容器資料保留，不刪 volume。
