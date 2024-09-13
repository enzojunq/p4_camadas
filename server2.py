from enlace import *

serialName = "COM3"  # Altere para a porta correta
com2 = enlace(serialName)

EOP = b'\xAA\xBB\xCC'  # 3 bytes

def is_datagram_complete(data):
    """Verifica se o datagrama está completo (HEAD + EOP)"""
    return data[-3:] == EOP

def receive_file():
    """Recebe um arquivo fragmentado em pacotes"""
    all_data = bytearray()
    expected_packets = None

    while True:
        datagram, _ = com2.getData(65)  # Tamanho máximo do datagrama (HEAD + PAYLOAD + EOP)
        
        if is_datagram_complete(datagram):
            packet_number = int.from_bytes(datagram[0:2], 'big')
            total_packets = int.from_bytes(datagram[2:4], 'big')
            payload_size = int.from_bytes(datagram[4:6], 'big')
            
            if expected_packets is None:
                expected_packets = total_packets
            
            payload = datagram[12:12+payload_size]
            all_data.extend(payload)

            print(f'Servidor: Pacote {packet_number}/{total_packets} recebido')

            # Enviar ACK
            ack_datagram = create_ack_datagram(packet_number)
            com2.sendData(ack_datagram)

            if packet_number == total_packets:
                print("Servidor: Todos os pacotes recebidos")
                break

    # Salvar o arquivo recebido
    with open('arquivo_recebido.txt', 'wb') as f:
        f.write(all_data)

def create_ack_datagram(packet_number):
    """Cria um datagrama ACK"""
    head = packet_number.to_bytes(2, 'big') + b'\x00'*10  # Cabeçalho com ACK
    return head + EOP

def main():
    try:
        com2.enable()

        # Aguardar handshake do cliente
        datagram, _ = com2.getData(15)
        if is_datagram_complete(datagram):
            print("Servidor: Handshake recebido, pronto para receber arquivo")
            ack_datagram = create_ack_datagram(0)
            com2.sendData(ack_datagram)

            receive_file()

        com2.disable()

    except Exception as e:
        print("Servidor: Ocorreu um erro:", e)
        com2.disable()

if __name__ == "__main__":
    main()
