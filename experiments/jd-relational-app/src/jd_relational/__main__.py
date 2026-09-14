"""Operator entry, using only the one OS-owned configuration location.

No alternate config-path/DSN/identity switches. Init is explicit; serving never
initializes or invokes a model. The employee UI and graphical launcher follow.
"""
import argparse
import getpass
import sys

from .config_file import ConfigFile, default_config_path
from .configured_host import initialize_configuration
from .local_configuration import parse_configuration
from .managed_app import open_managed_app, unavailable_consultant
from .provider_keys import ROLES, ProviderKeyError, configured_roles, remove_key, store_key


_MESSAGES = {
    "configuration_missing": "尚未找到本機設定。首次使用請明確初始化；已有資料時請先找回設定。",
    "configuration_exists": "初始化紀錄已存在，請查看狀態並使用原設定接續。",
    "configuration_busy": "另一個程序正在處理設定，請稍後再查看狀態。",
    "configuration_changed": "設定已變更，請關閉此程序後重新開啟。",
    "configuration_invalid": "本機設定無法讀取或版本不符；已保留原檔，未自動重建。",
    "configuration_write_unconfirmed": "設定保存結果尚未確認，請重新查看狀態後接續。",
    "configuration_initialization_required": "初始化尚未完成，請明確接續初始化。",
    "configuration_already_ready": "本機設定已完成初始化，可使用 serve 開啟服務。",
    "configuration_maintenance": "資料正在維護狀態，請完成原維護程序後再開啟。",
    "database_not_empty": "指定資料庫已有內容，已停止初始化並保留原資料。",
    "schema_mismatch": "資料格式與本版本不符，已停止且未自動修改。",
    "host_already_running": "此 App 已在執行，請使用原視窗或先正常關閉。",
    "host_storage_unavailable": "目前無法開啟資料，請確認資料庫服務與已完成的初始化。",
    "storage_unavailable": "目前無法確認初始化結果，請保留原設定並稍後查看狀態。",
    "unknown_provider_role": "沒有這個 AI 服務名稱。可設定的是 anthropic 或 openai。",
    "invalid_provider_key": "金鑰內容不符合格式，未保存；原有設定沒有變動。",
    "credential_write_failed": "Windows 認證管理員未確認保存，請重新查看狀態後再設定一次。",
    "credential_store_unavailable": "此作業系統沒有 Windows 認證管理員；AI 功能維持未啟用。",
    "stored_key_unreadable": "已保存的金鑰無法讀取；請重新設定該項，人工 JD 不受影響。",
}
# Naming a capability, never a key: nothing here prints or logs a stored value.
_ROLE_LABELS = {"anthropic": "訪談顧問（Anthropic）", "openai": "背景整理（OpenAI）"}
_PHASES = {
    "initialization_pending": "尚待驗證空資料庫；可使用 resume-init 接續。",
    "initializing": "初始化未完成；可使用 resume-init 接續。",
    "ready": "設定已初始化。serve 仍會檢查資料库與恢復狀態。",
    "maintenance": "維護中；普通開啟已暫停。",
}


def _connection_input():
    if not sys.stdin.isatty():
        raise ValueError("interactive_initialization_required")
    return dict(host="127.0.0.1", port=int(input("本機 PostgreSQL 連接埠：")),
        database=input("已建立的空資料庫名稱："), username=input("資料庫使用者："),
        password=getpass.getpass("資料庫密碼（不顯示）："), checkpoint_schema="jd_runtime",
        api_port=int(input("本機 API 連接埠：")),
        allowed_origins=(input("本機管理畫面來源，例如 http://127.0.0.1:3002："),))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Caliburn 關聯式 JD 本機服務；管理畫面與 AI 接合仍在施工。")
    parser.add_argument("action",
                        choices=("status", "init", "resume-init", "serve", "set-key", "remove-key"))
    parser.add_argument("--service", choices=ROLES,
                        help="set-key／remove-key 指定哪一項 AI 服務。")
    args = parser.parse_args(argv)
    try:
        file = ConfigFile(default_config_path())
        if args.action in {"set-key", "remove-key"}:
            if not args.service:
                print("請以 --service 指定 anthropic 或 openai。", file=sys.stderr)
                return 2
            if args.action == "remove-key":
                removed = remove_key(args.service)
                print(f"{_ROLE_LABELS[args.service]}：{'金鑰已移除' if removed else '原本就沒有金鑰'}。"
                      "人工 JD 不受影響。")
                return 0
            if not sys.stdin.isatty():
                raise ProviderKeyError("invalid_provider_key")
            # getpass keeps the key off the screen, the shell history and argv.
            store_key(args.service, getpass.getpass(
                f"{_ROLE_LABELS[args.service]} 金鑰（不顯示）："))
            print(f"{_ROLE_LABELS[args.service]}：金鑰已保存在 Windows 認證管理員。"
                  "此 App 的資料備份不會匯出金鑰；換電腦或還原後請重新設定。")
            return 0
        if args.action == "status":
            print(_PHASES[parse_configuration(file.read()).phase])
            for role, ready in configured_roles().items():
                # Configured is not proof the key works; finding that out costs money.
                print(f"{_ROLE_LABELS[role]}：{'已設定金鑰' if ready else '尚未設定，功能未啟用'}")
        elif args.action in {"init", "resume-init"}:
            initialize_configuration(file, connection=_connection_input() if args.action == "init" else None,
                resume=args.action == "resume-init")
            print("本機設定及資料結構已初始化。可使用 serve 開啟服務。")
        else:
            import uvicorn
            managed = open_managed_app(file, consultant=unavailable_consultant())
            try:
                uvicorn.run(managed.app, host="127.0.0.1", port=managed.port, workers=1,
                    reload=False, access_log=False, proxy_headers=False, log_level="warning")
            finally:
                if not managed.close():
                    print("服務仍有工作未確認結束，請保留此程序的診斷現場。", file=sys.stderr)
                    return 1
        return 0
    except (KeyboardInterrupt, EOFError):
        print("操作已中止；請重新查看實際保存狀態後再接續。", file=sys.stderr)
        return 130
    except Exception as error:
        code = getattr(error, "code", None)
        print(_MESSAGES.get(code, "操作未完成。請保留資料，確認本機設定及資料庫服務後再試。"), file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
