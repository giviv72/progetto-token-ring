#!/usr/bin/env python3
"""Quattro ATM, un token TCP, nessun servizio centrale o file condiviso."""
import argparse
import json
import queue
import socket
import sys
import threading
import time
from decimal import Decimal, InvalidOperation

HOST = "127.0.0.1"
BASE = 5100
MAX_MESSAGE = 1_000_000


def cents(text):
    """Importi esatti: niente arrotondamenti impliciti e niente float."""
    try:
        value = Decimal(str(text).replace(",", "."))
        if not value.is_finite() or value <= 0 or value * 100 != (value * 100).to_integral_value():
            raise ValueError("Importo positivo con massimo due decimali richiesto")
        return int(value * 100)
    except InvalidOperation as exc:
        raise ValueError("Importo non numerico") from exc


def money(value):
    return f"{value // 100}.{value % 100:02d} EUR"


def run(args):
    node = args.node
    successor = node % 4 + 1  # Unico peer conosciuto dal nodo.
    requests = queue.Queue()  # Coda locale, non condivisa fra processi.

    def log(event, **data):
        record = dict(time_ns=time.time_ns(), node=node, event=event, **data)
        print(json.dumps(record, ensure_ascii=False), flush=True)

    if args.demo:
        operation = {2: ("prelievo", 20000), 3: ("deposito", 10000),
                     4: ("prelievo", 50000)}.get(node)
        if operation:
            requests.put(operation)
    if args.operations:
        with open(args.operations, encoding="utf-8") as stream:
            for kind, amount in json.load(stream):
                if kind not in ("deposito", "prelievo"):
                    raise ValueError("Operazione sconosciuta")
                requests.put((kind, cents(amount)))

    # Il thread legge soltanto richieste locali. Non tocca mai il saldo.
    def console():
        for line in sys.stdin:
            words = line.strip().lower().split()
            if not words:
                continue
            if words == ["avvia"] and node == 1:
                requests.put(("avvia", 0))
            elif len(words) == 2 and words[0] in ("deposito", "prelievo"):
                try:
                    requests.put((words[0], cents(words[1])))
                    log("RICHIESTA_ACCETTATA", operation=words[0], amount=words[1])
                except ValueError as exc:
                    log("INPUT_NON_VALIDO", detail=str(exc))
            else:
                log("INPUT_NON_VALIDO", detail="Usare deposito 100 / prelievo 50 / avvia (ATM1)")

    threading.Thread(target=console, daemon=True).start()
    token = None
    initialized = False
    start_requested = False

    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as listener:
        listener.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        listener.bind((HOST, BASE + node))
        listener.listen(4)
        listener.settimeout(0.1)
        log("PRONTO", port=BASE + node, successor=successor)
        while True:
            if node == 1 and not initialized:
                # Cerca il comando avvia senza consumare le transazioni pendenti.
                buffered = []
                while not requests.empty():
                    item = requests.get_nowait()
                    if item[0] == "avvia":
                        start_requested = True
                    else:
                        buffered.append(item)
                for item in buffered:
                    requests.put(item)
                if start_requested:
                    initialized = True
                    token = dict(type="TOKEN", balance=100000, sequence=0, lap=1)
                    log("TOKEN_CREATO", balance=money(token["balance"]))

            if token is None:
                try:
                    conn, _ = listener.accept()
                except socket.timeout:
                    continue
                # Un messaggio JSON per connessione, terminato da newline.
                with conn:
                    conn.settimeout(5)
                    data = bytearray()
                    while not data.endswith(b"\n"):
                        part = conn.recv(4096)
                        if not part:
                            raise RuntimeError("Messaggio incompleto: arresto prudenziale")
                        data.extend(part)
                        if len(data) > MAX_MESSAGE:
                            raise RuntimeError("Messaggio troppo grande")
                token = json.loads(data)
                if token.get("type") != "TOKEN" or type(token.get("balance")) is not int:
                    raise RuntimeError("Token non valido")
                log("TOKEN_RICEVUTO", balance=money(token["balance"]), lap=token["lap"])
                if node == 1:
                    token["lap"] += 1
                    if args.rounds and token["lap"] > args.rounds:
                        log("DEMO_COMPLETATA", balance=money(token["balance"]),
                            transactions=token["sequence"])
                        return

            # Solo questo ramo, raggiungibile con token, modifica il saldo.
            try:
                operation, amount = requests.get_nowait()
            except queue.Empty:
                operation = None
            if operation == "avvia":
                operation = None  # Un secondo avvia non crea altri token.
            if operation:
                before = token["balance"]
                token["sequence"] += 1
                seq = token["sequence"]
                log("INIZIO_TRANSAZIONE", sequence=seq, operation=operation,
                    amount=money(amount), before=money(before))
                # Ritardo opzionale SOLO in sezione critica per renderla visibile.
                if args.critical_seconds:
                    time.sleep(args.critical_seconds)
                accepted = operation == "deposito" or amount <= before
                if accepted:
                    token["balance"] = before + amount if operation == "deposito" else before - amount
                log("FINE_TRANSAZIONE", sequence=seq,
                    status="ESEGUITA" if accepted else "RIFIUTATA_FONDI_INSUFFICIENTI",
                    after=money(token["balance"]))

            # Ritenta SOLO connect: nessun byte e' ancora stato inviato.
            # Dopo sendall non si ritenta: l'esito ambiguo potrebbe duplicare il token.
            while True:
                peer = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
                peer.settimeout(2)
                try:
                    peer.connect((HOST, BASE + successor))
                    break
                except (ConnectionRefusedError, socket.timeout):
                    peer.close()
                    log("SUCCESSORE_NON_PRONTO", successor=successor)
                    time.sleep(0.3)
            log("TOKEN_INOLTRO", successor=successor, balance=money(token["balance"]))
            with peer:
                peer.sendall((json.dumps(token) + "\n").encode())
            token = None  # Non accedere piu' allo stato ceduto.


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--node", type=int, choices=range(1, 5), required=True)
    parser.add_argument("--demo", action="store_true")
    parser.add_argument("--operations", help="JSON locale: [[tipo, importo], ...]")
    parser.add_argument("--rounds", type=int, default=0, help="Solo ATM1: 0 = continuo")
    parser.add_argument("--critical-seconds", type=float, default=0)
    args = parser.parse_args()
    if args.rounds < 0 or args.critical_seconds < 0 or (args.node != 1 and args.rounds):
        parser.error("Parametri temporali non validi; --rounds solo per ATM1")
    try:
        run(args)
    except KeyboardInterrupt:
        print(f"ATM{args.node}: arresto manuale", flush=True)
    except (OSError, ValueError, RuntimeError) as exc:
        print(f"ATM{args.node}: ARRESTO PRUDENZIALE: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
