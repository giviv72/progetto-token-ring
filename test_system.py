"""Test di integrazione: quattro processi reali, socket TCP su localhost."""
import json
import pathlib
import subprocess
import sys
import tempfile
import time

ROOT = pathlib.Path(__file__).resolve().parent


def scenario(name, operations=None, demo=False, rounds=1):
    processes = []
    with tempfile.TemporaryDirectory() as directory:
        try:
            for node in range(1, 5):
                command = [sys.executable, '-u', str(ROOT / 'atm.py'), '--node', str(node)]
                if demo:
                    command.append('--demo')
                if node == 1:
                    command += ['--rounds', str(rounds)]
                if operations and operations.get(node):
                    path = pathlib.Path(directory) / f'{node}.json'
                    path.write_text(json.dumps(operations[node]))
                    command += ['--operations', str(path)]
                process = subprocess.Popen(command, stdin=subprocess.PIPE,
                                           stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                           text=True)
                processes.append(process)
            # Legge PRONTO da ciascuno prima di inizializzare il token.
            prefixes = []
            for process in processes:
                line = process.stdout.readline()
                assert 'PRONTO' in line, line
                prefixes.append(line)
            processes[0].stdin.write('avvia\navvia\n')
            processes[0].stdin.flush()
            processes[0].wait(timeout=15)
            assert processes[0].returncode == 0
        finally:
            for process in processes:
                if process.poll() is None:
                    process.terminate()
            outputs = [p.communicate(timeout=5)[0] for p in processes]
    events = [json.loads(line) for output in [a+b for a,b in zip(prefixes, outputs)]
              for line in output.splitlines() if line.startswith('{')]
    events.sort(key=lambda event: event['time_ns'])
    # Gli intervalli reali di sezione critica non devono sovrapporsi.
    inside = None
    transactions = []
    for event in events:
        if event['event'] == 'INIZIO_TRANSAZIONE':
            assert inside is None, 'Sezioni critiche sovrapposte'
            inside = (event['node'], event['sequence'])
        elif event['event'] == 'FINE_TRANSAZIONE':
            assert inside == (event['node'], event['sequence'])
            inside = None
            transactions.append(event)
    assert inside is None
    assert sum(e['event'] == 'TOKEN_CREATO' for e in events) == 1
    final = next(e for e in events if e['event'] == 'DEMO_COMPLETATA')
    print(name, final['balance'], 'transazioni:', len(transactions))
    return events, transactions, final


def main():
    from atm import cents
    for invalid in ('0', '-1', '1.001', 'NaN', 'Infinity', 'abc'):
        try:
            cents(invalid)
        except ValueError:
            pass
        else:
            raise AssertionError(invalid)
    assert cents('0,01') == 1
    events, tx, final = scenario('Esempio della traccia', demo=True)
    assert [e['node'] for e in tx] == [2, 3, 4]
    assert [e['after'] for e in tx] == ['800.00 EUR', '900.00 EUR', '400.00 EUR']
    (ROOT / 'log_verificati.json').write_text(json.dumps(events, indent=2), encoding='utf-8')
    _, tx, final = scenario('Fondi insufficienti e centesimi',
        {1: [['prelievo','1000.01']], 2: [['deposito','0.01']],
         3: [['prelievo','0.01']], 4: [['prelievo','1000.00']]})
    assert tx[0]['status'] == 'RIFIUTATA_FONDI_INSUFFICIENTI'
    assert final['balance'] == '0.00 EUR'
    _, tx, final = scenario('Equita su piu giri',
        {n: [['deposito','1.00'], ['prelievo','0.50']] for n in range(1,5)}, rounds=3)
    assert [e['node'] for e in tx] == [1,2,3,4,1,2,3,4]
    assert final['balance'] == '1002.00 EUR'
    print('TUTTE LE VERIFICHE SUPERATE')


if __name__ == '__main__':
    main()
