# Sistema di transazioni bancarie distribuite con Token Ring

Progetto 1 della traccia. Quattro processi Python indipendenti su localhost;
comunicazione TCP e saldo autorevole trasportato esclusivamente dal token.

## Esecuzione

Richiede Python 3.10 o successivo, nessun pacchetto esterno, nessuna compilazione.
Aprire quattro terminali nella cartella del progetto e avviare:

```text
Terminale 1: python atm.py --node 1 --demo --rounds 1 --critical-seconds 2
Terminale 2: python atm.py --node 2 --demo --critical-seconds 2
Terminale 3: python atm.py --node 3 --demo --critical-seconds 2
Terminale 4: python atm.py --node 4 --demo --critical-seconds 2
```

Su Linux/macOS usare python3 se python non e' disponibile; su Windows e'
possibile usare py -3 al posto di python. Dopo PRONTO in tutti i terminali,
scrivere `avvia` e Invio nel terminale 1. L'ordine di apertura non importa.
Non avviare altre istanze dello stesso nodo.

Saldo iniziale 1000 EUR. ATM2 preleva 200, ATM3 deposita 100, ATM4 preleva 500:
saldo finale 400 EUR. Al ritorno del token ATM1 termina la demo; arrestare
gli altri tre processi con Ctrl+C. La pausa di 2 secondi opera solo nella
sezione critica, per rendere visibile la transazione.

## Modalita continua e interattiva

Nei quattro terminali usare `python atm.py --node N`, sostituendo N con
1, 2, 3, 4. Inserire `deposito 100.00` o `prelievo 50.00` nel terminale
desiderato; poi `avvia` nel terminale 1. Si possono inserire richieste anche
dopo l'avvio. Il token circola senza pause intenzionali sui nodi inattivi.
I log possono essere molto frequenti. Ctrl+C interrompe ciascun processo.
Per riavviare, fermare tutti i nodi e ripartire: lo stato non e' persistente.

Porte: ATM1 5101, ATM2 5102, ATM3 5103, ATM4 5104, tutte su 127.0.0.1.

## Test

```text
python test_system.py
```

Eseguire con le porte libere, senza altri ATM avviati. Tre scenari reali con
quattro sottoprocessi: esempio della traccia, fondi insufficienti e centesimi,
equita su piu giri. Verificati ordine, saldo, un solo token iniziale e assenza
di sovrapposizioni fra intervalli critici. Il test salva log_verificati.json.

## File

- atm.py: sorgente completo commentato.
- test_system.py: verifiche riproducibili.
- log_verificati.json: log dell'esempio verificato.
- video_dimostrativo.mp4: 15 secondi senza tagli; flussi di quattro
  pseudoterminali reali, affiancati in un unico video. Non e' una ripresa
  di quattro finestre desktop; se il docente richiede finestre native,
  registrare lo stesso avvio nei quattro terminali del proprio computer.
- registrazione_terminali.json: acquisizione temporale originale del video.
- Relazione_Token_Ring.pdf: relazione, istruzioni e codice completo.

## Limiti dichiarati

Modello didattico senza guasti, riavvii o peer ostili durante l'esecuzione.
TCP preserva i byte; non fornisce un commit distribuito durevole. Gli errori
di invio portano ad arresto prudenziale senza reinviare il token. Non sono
implementati recupero del token, persistenza, autenticazione o uso bancario reale.
Il thread di input e la sua Queue sono solo locali al singolo processo.

## Repository personale

https://github.com/giviv72/progetto-token-ring

Il repository pubblico contiene codice completo, test, log, video e relazione PDF.
Il documento da caricare sulla piattaforma universitaria e' Relazione_Token_Ring.pdf.
