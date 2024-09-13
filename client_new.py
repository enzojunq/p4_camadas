import time
import datetime
import binascii
from enlace import *

# Configurar a porta serial
serialName = "/dev/tty.usbmodem2101"  # Altere para a porta correta
com1 = enlace(serialName)

# Configurações do EOP
EOP = b'\xAA\xBB\xCC'  # 3 bytes

def calculate_crc(payload):
    crc = binascii.crc_hqx(payload, 0xFFFF)
    return crc

def create_datagram(packet_number, total_packets, payload, fake_payload_size=None):
    payload_size = fake_payload_size if fake_payload_size is not None else len(payload)
    crc = calculate_crc(payload)
    message_type = 3  # Data packet
    
    head = (packet_number.to_bytes(2, 'big') +
            total_packets.to_bytes(2, 'big') +
            payload_size.to_bytes(2, 'big') +
            crc.to_bytes(2, 'big') +
            message_type.to_bytes(1, 'big') +
            b'\x00'*3)
    
    return head + payload + EOP

def handshake():
    # Enviar byte de sacrifício para eliminar "lixo"
    time.sleep(0.2)
    com1.sendData(b'00')  # Byte de sacrifício
    time.sleep(1)

    message_type = 1  # Handshake
    head = (b'\x00'*8 + message_type.to_bytes(1, 'big') + b'\x00'*3)
    datagram = head + EOP  # Handshake payload vazio
    com1.sendData(datagram)
    print("Cliente: Enviando mensagem de handshake...")
    log_event('envio', message_type, len(datagram))
    response, _ = com1.getData(15)  # Tamanho total do datagrama esperado (HEAD + EOP)
    if response:
        head = response[:12]
        message_type = head[8]
        log_event('receb', message_type, len(response))
        if message_type == 2:
            print("Cliente: Handshake bem-sucedido")
            return True
        else:
            print("Cliente: Resposta inesperada no handshake")
            return False
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
        size = len(datagram)
        crc_value = calculate_crc(payload)
        log_event('envio', 3, size, packet_index + 1, total_packets, crc_value)
        print(f'Cliente: Pacote {packet_index + 1} enviado \n\n')

        # Aguardar ACK ou NACK
        response, _ = com1.getData(15)  # 15 bytes para o datagrama do ACK/NACK

        # Verifica se é ACK ou NACK
        if response:
            head = response[:12]
            message_type = head[8]  # O 9º byte é message_type
            log_event('receb', message_type, len(response))
            if message_type == 4:  # ACK
                print(f'Cliente: ACK recebido para pacote {packet_index + 1}')
                packet_index += 1  # Prossegue para o próximo pacote
            elif message_type == 5:  # NACK
                print(f'Cliente: NACK recebido para pacote {packet_index + 1}. Reenviando...')
                # Não incrementa o índice, reenvia o mesmo pacote
        else:
            print(f'Cliente: Erro no pacote {packet_index + 1}, tentando novamente...')
            continue

def log_event(event_type, message_type, size, packet_number=None, total_packets=None, crc=None):
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")[:-3]
    with open('client_log.txt', 'a') as log_file:
        line = f"{timestamp} / {event_type} / {message_type} / {size}"
        if packet_number is not None and total_packets is not None and crc is not None:
            line += f" / {packet_number} / {total_packets} / {crc:04X}"
        log_file.write(line + "\n")

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
        print("Arquivo enviado com sucesso!")

    except Exception as e:
        print("Cliente: Ocorreu um erro:", e)
        com1.disable()

if __name__ == "__main__":
    main()
