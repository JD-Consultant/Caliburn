"""Operator entry, using only the one OS-owned configuration location.

No alternate config-path/DSN/identity switches. Init is explicit. Serving only
enables the completed consultant when its OpenRouter credential exists; startup
itself never sends a model request. The graphical launcher follows.
"""
import argparse
import getpass
import sys

from .config_file import ConfigFile, default_config_path
from .configured_host import initialize_configuration
from .consultant_runtime import open_consultant_runtime
from .local_configuration import ConfigurationError, parse_configuration
from .managed_app import open_managed_app, unavailable_consultant
from .provider_keys import (
    ROLES, ProviderKeyError, configured_roles, read_key, remove_key, store_key,
)


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
    "unknown_provider_role": "沒有這個 AI 服務名稱。目前只使用 OpenRouter。",
    "invalid_provider_key": "金鑰內容不符合格式，未保存；原有設定沒有變動。",
    "credential_write_failed": "Windows 認證管理員未確認保存，請重新查看狀態後再設定一次。",
    "credential_delete_failed": "Windows 認證管理員未確認移除；金鑰可能仍在，請重新查看狀態後再移除一次。",
    "interactive_key_entry_required": "設定金鑰需要可輸入的終端機；金鑰不從命令參數或環境傳入。",
    "credential_store_unavailable": "此作業系統沒有 Windows 認證管理員；AI 功能維持未啟用。",
    "stored_key_unreadable": "已保存的金鑰無法讀取；請重新設定該項，人工 JD 不受影響。",
}
# Naming a capability, never a key: nothing here prints or logs a stored value.
_ROLE_LABELS = {"openrouter": "LLM 顧問（OpenRouter）"}
_PHASES = {
    "initialization_pending": "尚待驗證空資料庫；可使用 resume-init 接續。",
    "initializing": "初始化未完成；可使用 resume-init 接續。",
    "ready": "設定已初始化。serve 仍會檢查資料库與恢復狀態。",
    "maintenance": "維護中；普通開啟已暫停。",
}


def _close(resource):
    if resource is None:
        return True
    try:
        return bool(resource.close())
    except Exception:
        return False


def _connection_input():
    if not sys.stdin.isatty():
        raise ValueError("interactive_initialization_required")
    return dict(host="127.0.0.1", port=int(input("本機 PostgreSQL 連接埠：")),
        database=input("已建立的空資料庫名稱："), username=input("資料庫使用者："),
        password=getpass.getpass("資料庫密碼（不顯示）："), checkpoint_schema="jd_runtime",
        api_port=int(input("本機 API 連接埠：")),
        allowed_origins=(input("本機管理畫面來源，例如 http://127.0.0.1:3002："),))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Caliburn 關聯式 JD 本機服務。")
    parser.add_argument("action",
                        choices=("status", "api-origin", "init", "resume-init", "serve",
                                 "set-key", "remove-key"))
    parser.add_argument("--service", choices=ROLES,
                        help="set-key／remove-key 指定哪一項 AI 服務。")
    args = parser.parse_args(argv)
    try:
        file = ConfigFile(default_config_path())
        if args.action in {"set-key", "remove-key"}:
            if not args.service:
                print("請以 --service 指定 openrouter。", file=sys.stderr)
                return 2
            if args.action == "remove-key":
                removed = remove_key(args.service)
                print(f"{_ROLE_LABELS[args.service]}：{'金鑰已移除' if removed else '原本就沒有金鑰'}。"
                      "人工 JD 不受影響。")
                return 0
            if not sys.stdin.isatty():
                # Nothing is wrong with the key; there is nowhere to type it.
                raise ProviderKeyError("interactive_key_entry_required")
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
        elif args.action == "api-origin":
            settings = parse_configuration(file.read())
            if settings.phase != "ready":
                code = ("configuration_maintenance" if settings.phase == "maintenance"
                        else "configuration_initialization_required")
                raise ConfigurationError(code)
            print(f"http://127.0.0.1:{settings.api_port}")
        elif args.action in {"init", "resume-init"}:
            initialize_configuration(file, connection=_connection_input() if args.action == "init" else None,
                resume=args.action == "resume-init")
            print("本機設定及資料結構已初始化。可使用 serve 開啟服務。")
        else:
            import uvicorn
            runtime = None
            managed = None
            try:
                key = read_key("openrouter")
                if key is None:
                    consultant = unavailable_consultant()
                    enable_chat = False
                else:
                    runtime = open_consultant_runtime(api_key=key)
                    del key
                    consultant = runtime.graph
                    enable_chat = True
                managed = open_managed_app(
                    file,
                    consultant=consultant,
                    enable_chat=enable_chat,
                    case_model=runtime.role_models.case if runtime is not None else None,
                    understanding_model=(
                        runtime.role_models.understanding if runtime is not None else None
                    ),
                )
                uvicorn.run(managed.app, host="127.0.0.1", port=managed.port, workers=1,
                    reload=False, access_log=False, proxy_headers=False, log_level="warning")
            finally:
                app_closed = _close(managed)
                consultant_closed = _close(runtime) if app_closed else True
                if not app_closed or not consultant_closed:
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
