import threading
import time
import serpent
import os
import sys
from Pyro5.api import locate_ns, Proxy
import ultimatePeer

peer_names = [f"{i}" for i in range(1, 6)]

peer_name = sys.argv[1]
port = 50000 + int(peer_name)
peer_uri = None

def runner(name, port):
    daemon, uri = ultimatePeer.start(name, "localhost", port, peer_names)
    global peer_uri
    peer_uri = uri
    daemon.requestLoop()

thread = threading.Thread(target=runner, args=(peer_name, port), daemon=True)
thread.start()
time.sleep(0.1)

def get_tracker_proxy():
    ns = locate_ns("localhost", 9090)
    trackers = ns.list(prefix="Tracker_Epoca_")
    if not trackers:
        return None
    epoch = max(trackers, key=lambda k: int(k.rsplit("_", 1)[1]))
    return Proxy(trackers[epoch])

peer_proxy = Proxy(peer_uri)

while True:
    print(f"\n[peer.{peer_name}] Opções:")
    print("1) Listar arquivos de outros peers (via tracker)")
    print("2) Baixar arquivo")
    print("3) Listar meus arquivos")
    print("4) Desconectar este peer")
    op = input("Escolha uma opção: ").strip()

    tracker_proxy = get_tracker_proxy()

    if op == "1":
        if not tracker_proxy:
            print("Nenhum tracker disponível.")
            continue
        print("\nArquivos indexados no tracker:")
        for pid in peer_names:
            try:
                files = tracker_proxy.get_index(pid)
                if files:
                    print(f"peer.{pid}: ", end="")
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
        if not os.path.exists(peer_name + "received"):
            os.makedirs(peer_name + "received")
        with open(peer_name + "received/" + fname, "wb") as f:
            f.write(data)
        print(f"Arquivo {fname} salvo em {peer_name}received/{fname}")

    elif op == "3":
        files = peer_proxy.get_file_list()
        print("Seus arquivos:", ", ".join(files))

    elif op == "4":
        print(f"Desconectando peer.{peer_name}...")
        # encerramento bruto, sem daemon.shutdown() pois daemon roda em thread
        if peer_proxy.get_is_tracker():
            print("Era o tracker, aguardando nova eleição...")
            peer_proxy.set_not_tracker()
        thread.join(timeout=1.0)

        break

    else:
        print("Opção inválida.")
