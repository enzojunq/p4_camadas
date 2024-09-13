import time
from enlace import *

# Configurar a porta serial
serialName = "/dev/tty.usbmodem2101"  # Altere para a porta correta
com1 = enlace(serialName)

# Configurações do EOP
EOP = b'\xAA\xBB\xCC'  # 3 bytes

def create_datagram(packet_number, total_packets, payload, fake_payload_size=None):
    
    payload_size = fake_payload_size if fake_payload_size is not None else len(payload)
    
    head = packet_number.to_bytes(2, 'big') + total_packets.to_bytes(2, 'big') + payload_size.to_bytes(2, 'big') + b'\x00'*6
    
    return head + payload + EOP

def handshake():
    
    
    
    # Enviar byte de sacrifício para eliminar "lixo"
    time.sleep(0.2)
    com1.sendData(b'00')  # Byte de sacrifício
    time.sleep(1)

    
    datagram = create_datagram(0, 0, b'')  # Handshake payload vazio
    com1.sendData(datagram)
    print("Cliente: Enviando mensagem de handshake...")
    response, _ = com1.getData(15)  # Tamanho total do datagrama esperado (HEAD + EOP)
    if response:
        print("Cliente: Handshake bem-sucedido")
        return True
    else:
        print("Cliente: Handshake falhou")
        return False

def send_file(file_path):
    """Envia um arquivo fragmentado em pacotes"""
    with open(file_path, 'rb') as file:
        content = file.read()

    total_packets = (len(content) + 49) // 50  # Calcula o número total de pacotes
    packet_index = 0

    while packet_index < total_packets:
        start = packet_index * 50
        end = min((packet_index + 1) * 50, len(content))
        payload = content[start:end]

        erro_payload = False
        
        # Simulando erro_payload de tamanho no cabeçalho para o pacote 2
        if erro_payload:
            print(f"Cliente: Simulando erro no tamanho do payload no cabeçalho para o pacote 2.")
            datagram = create_datagram(packet_index + 1, total_packets, payload, fake_payload_size=40)  # Simulando erro (tamanho incorreto 40)
        else:
            # erro numero do pacotes
            datagram = create_datagram(packet_index + 1, total_packets, payload)

        com1.sendData(datagram)
        print(f'Cliente: Pacote {packet_index + 1} enviado \n\n')

        # Aguardar ACK ou NACK
        response, _ = com1.getData(15)  # 15 bytes para o datagrama do ACK/NACK

        # Verifica se é ACK ou NACK
        if response:
            packet_type = response[4]  # O 5º byte indicará ACK (0) ou NACK (1)
            if packet_type == 0:  # ACK
                print(f'Cliente: ACK recebido para pacote {packet_index + 1}')
                packet_index += 1  # Prossegue para o próximo pacote
            elif packet_type == 1:  # NACK
                print(f'Cliente: NACK recebido para pacote {packet_index + 1}. Reenviando...')
                # Não incrementa o índice, reenvia o mesmo pacote
        else:
            print(f'Cliente: Erro no pacote {packet_index + 1}, tentando novamente...')
            continue
def main():
    try:
        com1.enable()
        
        handshake_successful = False

        while not handshake_successful:
            if handshake():
                handshake_successful = True
                file_path = 'arquivo.txt'  # Altere para o caminho correto do arquivo
                send_file(file_path)
            else:
                print("Servidor inativo. Tentar novamente? S/N")
                retry = input().lower()
                if retry != 's':
                    com1.disable()  # Desabilitar comunicação antes de sair
                    return
                else:
                    print("Tentando novamente o handshake...")


        com1.disable()

    except Exception as e:
        print("Cliente: Ocorreu um erro:", e)
        com1.disable()

if __name__ == "__main__":
    main()
    print("Arquivo enviado com sucesso!")