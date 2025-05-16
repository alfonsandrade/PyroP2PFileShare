import threading
import time
import serpent
from Pyro5.api import locate_ns, Proxy
import ultimatePeer

peer_names = [f"{i}" for i in range(1, 6)]
ports = list(range(50000, 50000 + len(peer_names)))
uris = {}
threads = {}

def runner(name, port):
    daemon, uri = ultimatePeer.start(name, "localhost", port, peer_names)
    uris[name] = uri
    daemon.requestLoop()

for n, p in zip(peer_names, ports):
    threads[n] = threading.Thread(target=runner, args=(n, p), daemon=True)
    threads[n].start()
    time.sleep(0.1)

while len(uris) < len(peer_names):
    time.sleep(0.05)

def get_tracker_proxy():
    ns = locate_ns("localhost", 9090)
    trackers = ns.list(prefix="Tracker_Epoca_")
    if not trackers:
        return None
    epoch = max(trackers, key=lambda k: int(k.rsplit("_", 1)[1]))
    return Proxy(trackers[epoch])

while True:
    print("\nPeers disponíveis:")
    for i, name in enumerate(peer_names):
        print(f"{i+1}) peer.{name}")
    sel = input("Selecione o número do peer (ou 'q' para sair): ").strip()
    if sel == 'q':
        break
    if not sel.isdigit() or not (1 <= int(sel) <= len(peer_names)):
        print("Entrada inválida.")
        continue

    peer_id = peer_names[int(sel) - 1]
    peer_proxy = Proxy(uris[peer_id])
    tracker_proxy = get_tracker_proxy()

    while True:
        print(f"\n[peer.{peer_id}] Opções:")
        print("1) Listar arquivos de outros peers (via tracker)")
        print("2) Baixar arquivo")
        print("3) Listar meus arquivos")
        print("4) Desconectar este peer")
        print("0) Voltar")
        op = input("Escolha uma opção: ").strip()

        if op == "0":
            break

        elif op == "1":
            if not tracker_proxy:
                print("Nenhum tracker disponível.")
                continue
            print("\nArquivos indexados no tracker:")
            for pid in peer_names:
                print(f"peer.{pid}: ", end="")
                try:
                    files = tracker_proxy.index[pid]
                    print(", ".join(files))
                except:
                    print("(indisponível)")

        elif op == "2":
            fname = input("Nome do arquivo a baixar: ").strip()
            if not tracker_proxy:
                print("Nenhum tracker disponível.")
                continue
            owners = tracker_proxy.query(fname)
            if not owners:
                print("Arquivo não encontrado.")
                continue
            owner_proxy = Proxy(owners[0])
            data = owner_proxy.file_transfer(fname)
            if isinstance(data, dict):
                data = serpent.tobytes(data)
            if not isinstance(data, (bytes, bytearray)):
                raise TypeError(f"Esperado bytes, recebido {type(data)}")
            with open("received_" + fname, "wb") as f:
                f.write(data)
            print(f"Arquivo {fname} salvo como received_{fname}")

        elif op == "3":
            files = peer_proxy.get_file_list()
            print("Seus arquivos:", ", ".join(files))

        elif op == "4":
            print(f"Desconectando peer.{peer_id}...")
            # encerramento bruto, sem daemon.shutdown() pois daemon roda em thread
            if peer_proxy.get_is_tracker():
                print("Era o tracker, aguardando nova eleição...")
                time.sleep(1.0)
            del uris[peer_id]
            threads[peer_id].join(timeout=1.0)

            break

        else:
            print("Opção inválida.")
