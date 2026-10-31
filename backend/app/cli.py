"""``nit`` CLI — a thin httpx client of the running backend (ARCHITECTURE §8).

The backend is the single write path (ADR-004): this module never opens the DB
or the evidence tree, and it never fetches X. The user assembles URL lists from
what they already looked at; the archive services do the fetching.

Run from ``backend/`` with the backend up:  ``python -m app.cli --help``
"""

from __future__ import annotations

import json
import webbrowser
from pathlib import Path
from typing import Annotated

import httpx
import typer

from app.config import BIND_HOST, get_settings

app = typer.Typer(help="News Integrity TR — kanıt arşivi yardımcı komutları.", no_args_is_help=True)
pending_app = typer.Typer(help="Tamamlanmayı bekleyen (CLI ile sıraya alınmış) gönderiler.", no_args_is_help=True)
archive_app = typer.Typer(help="Arşiv kuyruğu: elle tamamlama döngüsü.", no_args_is_help=True)
export_app = typer.Typer(help="Dışa aktarımlar.", no_args_is_help=True)
app.add_typer(pending_app, name="pending")
app.add_typer(archive_app, name="archive")
app.add_typer(export_app, name="export")

SERVICE_LABEL = {"wayback": "Wayback Machine", "archive_today": "archive.today"}


def make_client() -> httpx.Client:
    """Replaced in tests with the app's TestClient (also an httpx.Client)."""
    return httpx.Client(base_url=f"http://{BIND_HOST}:{get_settings().port}", timeout=30.0)


def _call(method: str, path: str, **kwargs) -> httpx.Response:
    try:
        with make_client() as client:
            response = client.request(method, path, **kwargs)
    except httpx.ConnectError:
        typer.secho(
            "Backend'e ulaşılamadı. Önce başlat: backend/ içinde `python -m app.main`.",
            fg=typer.colors.RED,
            err=True,
        )
        raise typer.Exit(2) from None
    if response.status_code >= 400:
        try:
            detail = response.json().get("detail")
        except ValueError:
            detail = response.text
        typer.secho(f"Hata ({response.status_code}): {detail}", fg=typer.colors.RED, err=True)
        raise typer.Exit(1)
    return response


def _write_or_print(text: str, output: Path | None) -> None:
    if output is None:
        typer.echo(text)
        return
    output.write_text(text, encoding="utf-8", newline="\n")
    typer.secho(f"Yazıldı: {output}", fg=typer.colors.GREEN)


@app.command("bulk-archive")
def bulk_archive(
    handle: Annotated[str, typer.Option(help="Hesabın kullanıcı adı (@ olmadan).")],
    urls_file: Annotated[Path, typer.Option(exists=True, dir_okay=False, help="Satır başına bir gönderi bağlantısı.")],
    rest_id: Annotated[str | None, typer.Option(help="Hesap henüz tanınmıyorsa sayısal X kimliği.")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y", help="Onay sormadan çalıştır.")] = False,
) -> None:
    """Gönderileri hemen arşiv kuyruğuna al; tam kanıtı sonra tarayıcıda tamamla."""
    urls = [
        line.strip()
        for line in urls_file.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.lstrip().startswith("#")
    ]
    if not urls:
        typer.secho("Dosyada bağlantı yok.", fg=typer.colors.YELLOW)
        raise typer.Exit(1)
    handle = handle.lstrip("@")
    who = f"@{handle}" + (f" (rest_id {rest_id})" if rest_id else "")
    if not yes and not typer.confirm(
        f"{who} için {len(urls)} bağlantı sıraya alınacak ve her biri için iki arşiv işi açılacak. Devam?"
    ):
        raise typer.Exit(0)
    account = {"handle": handle, **({"rest_id": rest_id} if rest_id else {})}
    body = _call("POST", "/api/cli/bulk-archive", json={"account": account, "urls": urls}).json()
    acc = body["account"]
    typer.secho(
        f"{len(body['created'])} gönderi sıraya alındı → hesap {acc['account_id']} (@{acc['handle']})",
        fg=typer.colors.GREEN,
    )
    for item in body["created"]:
        typer.echo(f"  #{item['evidence_id']:<5} seq {item['seq']:04d}  {item['post_url']}")
    if body["skipped"]:
        typer.secho(f"{len(body['skipped'])} bağlantı atlandı:", fg=typer.colors.YELLOW)
        for item in body["skipped"]:
            typer.echo(f"  {item['url']}  — {item['reason']}")


@pending_app.command("list")
def pending_list() -> None:
    """Tamamlama listesi: her bağlantıyı açıp eklentiyle [Yakala]'ya bas."""
    rows = _call("GET", "/api/pending").json()
    if not rows:
        typer.secho("Bekleyen gönderi yok.", fg=typer.colors.GREEN)
        return
    typer.echo(f"{len(rows)} gönderi tamamlanmayı bekliyor:")
    for row in rows:
        typer.echo(f"  #{row['evidence_id']:<5} {row['phase']} seq {row['seq']:04d}  {row['post_url']}")


@pending_app.command("archive-only")
def pending_archive_only(
    evidence_id: int,
    note: Annotated[str | None, typer.Option(help="Neden (ör. 'gönderi silinmiş').")] = None,
    yes: Annotated[bool, typer.Option("--yes", "-y")] = False,
) -> None:
    """Silinmiş gönderiyi yalnız-arşiv kanıtına düşür (geri alınamaz)."""
    if not yes and not typer.confirm(
        f"#{evidence_id} yalnız-arşiv olarak işaretlenecek; ekran görüntüsü hiç eklenemeyecek. Devam?"
    ):
        raise typer.Exit(0)
    row = _call("POST", f"/api/evidence/{evidence_id}/archive-only", json={"note": note}).json()
    typer.secho(f"#{row['evidence_id']} artık {row['status']}.", fg=typer.colors.GREEN)


def _open_jobs() -> list[dict]:
    jobs = _call("GET", "/api/archive/jobs", params={"status": "manual_pending"}).json()
    jobs += _call("GET", "/api/archive/jobs", params={"status": "failed"}).json()
    return sorted(jobs, key=lambda j: j["id"])


@archive_app.command("pending")
def archive_pending() -> None:
    """Elle tamamlanmayı bekleyen arşiv işleri (manual_pending + failed)."""
    jobs = _open_jobs()
    if not jobs:
        typer.secho("Elle bekleyen arşiv işi yok.", fg=typer.colors.GREEN)
        return
    for job in jobs:
        typer.echo(
            f"  iş #{job['id']:<5} kanıt #{job['evidence_id']:<5} {SERVICE_LABEL[job['service']]:<16} "
            f"{job['status']:<15} {job['target_url']}"
        )
        if job["last_error"]:
            typer.echo(f"           ↳ {job['last_error']}")


@archive_app.command("manual")
def archive_manual(
    open_browser: Annotated[bool, typer.Option("--browser/--no-browser", help="Gönderim sayfasını tarayıcıda aç.")] = True,
) -> None:
    """Döngü: gönderim sayfasını aç → arşivle → bağlantıyı buraya yapıştır."""
    jobs = _open_jobs()
    if not jobs:
        typer.secho("Elle bekleyen arşiv işi yok.", fg=typer.colors.GREEN)
        return
    done = 0
    for index, job in enumerate(jobs, start=1):
        typer.echo("")
        typer.secho(
            f"[{index}/{len(jobs)}] {SERVICE_LABEL[job['service']]} · kanıt #{job['evidence_id']} · {job['target_url']}",
            bold=True,
        )
        typer.echo(f"Gönderim sayfası: {job['submit_page']}")
        if open_browser:
            webbrowser.open(job["submit_page"])
        while True:
            pasted = typer.prompt(
                "Arşiv bağlantısını yapıştır (boş: atla, q: bitir)", default="", show_default=False
            ).strip()
            if pasted.lower() == "q":
                typer.secho(f"{done} iş tamamlandı.", fg=typer.colors.GREEN)
                return
            if not pasted:
                break
            with make_client() as client:
                response = client.post(f"/api/archive/jobs/{job['id']}/manual", json={"archive_url": pasted})
            if response.status_code == 200:
                done += 1
                typer.secho("Kaydedildi.", fg=typer.colors.GREEN)
                break
            typer.secho(f"Kabul edilmedi: {response.json().get('detail')}", fg=typer.colors.RED)
    typer.secho(f"{done} iş tamamlandı.", fg=typer.colors.GREEN)


@archive_app.command("retry")
def archive_retry(job_id: int) -> None:
    """Başarısız ya da elle bekleyen bir işi otomatik kuyruğa geri koy."""
    job = _call("POST", f"/api/archive/jobs/{job_id}/retry").json()
    typer.secho(f"iş #{job['id']} yeniden kuyrukta ({job['status']}).", fg=typer.colors.GREEN)


@export_app.command("edges")
def export_edges(output: Annotated[Path | None, typer.Option("-o", "--output")] = None) -> None:
    """Etkileşim kenarları (CSV)."""
    _write_or_print(_call("GET", "/api/exports/edges.csv").text, output)


@export_app.command("case-file")
def export_case_file(
    account_id: str, output: Annotated[Path | None, typer.Option("-o", "--output")] = None
) -> None:
    """Bir hesabın tüm kanıt dosyası (JSON)."""
    body = _call("GET", f"/api/exports/accounts/{account_id}/case-file.json").json()
    _write_or_print(json.dumps(body, ensure_ascii=False, indent=2), output)


@export_app.command("manifest")
def export_manifest(
    verify: Annotated[bool, typer.Option("--verify", help="Diskteki dosyaları yeniden hash'le.")] = False,
    output: Annotated[Path | None, typer.Option("-o", "--output")] = None,
) -> None:
    """Tüm kanıt dosyalarının SHA-256 listesi; --verify ile diskle karşılaştırır."""
    body = _call("GET", "/api/exports/manifest", params={"verify": str(verify).lower()}).json()
    _write_or_print(json.dumps(body, ensure_ascii=False, indent=2), output)
    if verify:
        bad, untracked = body["mismatches"], body["untracked"]
        if not bad and not untracked:
            typer.secho(f"Doğrulandı: {len(body['entries'])} dosyanın hepsi eşleşiyor.", fg=typer.colors.GREEN, err=True)
            return
        for item in bad:
            typer.secho(f"{item['verify'].upper():<9} {item['path']}", fg=typer.colors.RED, err=True)
        for path in untracked:
            typer.secho(f"KAYITSIZ  {path}", fg=typer.colors.YELLOW, err=True)
        raise typer.Exit(1)


if __name__ == "__main__":
    app()
