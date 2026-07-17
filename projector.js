(() => {
  'use strict';

  const PROJECTOR_TYPES = new Map([
    ['3:3:3', {id: 'Animal', label: 'Fauna', vpCount: 3}],
    ['4:2:2', {id: 'Flora', label: 'Flora', vpCount: 2}],
    ['5:2:2', {id: 'Mineral', label: 'Mineral', vpCount: 2}],
  ]);

  function normalizeBase64(value) {
    const compact = String(value || '').trim().replace(/\s+/g, '').replace(/-/g, '+').replace(/_/g, '/');
    if (!compact) throw new Error('Enter a Wonder Projector Message ID first.');
    if (compact.length % 4 === 1 || !/^[A-Za-z0-9+/]*={0,2}$/.test(compact)) {
      throw new Error('That does not look like a valid Wonder Projector Message ID.');
    }
    const unpadded = compact.replace(/=+$/, '');
    return unpadded + '='.repeat((4 - (unpadded.length % 4)) % 4);
  }

  function decodeBytes(value) {
    let binary;
    try {
      binary = atob(normalizeBase64(value));
    } catch (error) {
      if (error instanceof Error && error.message.startsWith('Enter a Wonder')) throw error;
      throw new Error('That Message ID could not be decoded. Check that the complete value was pasted.');
    }
    return Uint8Array.from(binary, (character) => character.charCodeAt(0));
  }

  function readUInt64LittleEndian(bytes, offset) {
    let value = 0n;
    for (let index = offset + 7; index >= offset; index -= 1) {
      value = (value << 8n) | BigInt(bytes[index]);
    }
    return value;
  }

  function decodeMessageId(value) {
    const bytes = decodeBytes(value);
    if (bytes.length < 16 || (bytes.length - 16) % 8 !== 0) {
      throw new Error('This payload is not a supported Wonder Projector Message ID.');
    }

    const view = new DataView(bytes.buffer, bytes.byteOffset, bytes.byteLength);
    const typeCode = view.getInt32(8, true);
    const layoutCode = view.getInt32(12, true);
    const vpCount = (bytes.length - 16) / 8;
    const projectorType = PROJECTOR_TYPES.get(`${typeCode}:${layoutCode}:${vpCount}`);
    if (!projectorType) {
      throw new Error('This projector format is not supported yet. Fauna, flora, and mineral Message IDs are supported.');
    }

    const universalAddress = readUInt64LittleEndian(bytes, 0);
    if (universalAddress >= (1n << 56n)) {
      throw new Error('The Message ID contains an invalid Universal Address.');
    }

    return {
      messageId: normalizeBase64(value),
      universalAddress,
      universalAddressHex: universalAddress.toString(16).toUpperCase().padStart(14, '0'),
      typeCode,
      layoutCode,
      vpCount,
      discoveryType: projectorType.id,
      discoveryLabel: projectorType.label,
    };
  }

  window.WCProjector = {decodeMessageId};
})();
