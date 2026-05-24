/* Exifr — extract EXIF from images — UMD build 
   Source: https://github.com/MikeDemirkel/exifr
   Version: v3.2.0
   Latest commit: 2023-12-07
*/

(function (global, factory) {
  typeof exports === 'object' && typeof module !== 'undefined' ? module.exports = factory() :
  typeof define === 'function' && define.amd ? define(factory) :
  (global = typeof globalThis !== 'undefined' ? globalThis : global || self, global.exifr = factory());
}(this, (function () {
    'use strict';

    var commonjsGlobal = typeof globalThis !== 'undefined' ? globalThis : typeof window !== 'undefined' ? window : global;

    var hasRequiredThese = { '__commonjs-module__': true };

    function getAugmentedNamespace(n) {
        if (hasRequiredThese.__commonjs-module__) {
            return n;
        }
        var m = Object.assign({}, n);
        if (n && typeof n.default === 'object' && n.default.__esModule) {
            Object.keys(n.default).forEach(function (key) {
                if (key !== 'default') {
                    Object.defineProperty(m, key, { enumerable: true, get: function () { return n.default[key]; } });
                }
            });
        }
        hasRequiredThese.__commonjs-module__ = true;
        return m;
    }

    function esmRequire(id) {
        if (id === './utils') return getAugmentedNamespace(require("./utils.js"));
        throw new Error('Cannot find module "' + id + '"');
    }

    function interopRequireDefault(obj) {
        return obj && obj.__esModule ? obj : {
            default: obj
        };
    }

    function createCommonjsModule(fn, module) {
        return fn(module = { exports: {} }, module.exports),
            module.exports;
    }

    var utils = createCommonjsModule(function (module, exports) {
        Object.defineProperty(exports, '__esModule', {
            value: true
        });
        exports.uint16LE = exports.uint16BE = exports.uint8 = exports.bufferSplitter = exports.defaultTags = exports.toTypedArray = exports.isBuffer = exports.exists = exports.byteAlign = exports.dataToTypedArray = exports.dataSlice = exports.dateTimezone = exports.parseDate = exports.parseRational = exports.parseGPSDate = exports.parseGPSCoordinate = exports.parseAscii = exports.parseRational = exports.parseUndefined = exports.parseSByte = exports.parseByte = exports.parseSShort = exports.parseShort = exports.parseSLong = exports.parseLong = exports.tagNames = exports.tiffTags = exports.gpsTags = exports.exifTags = exports.iptcTags = exports.parseEXIF = exports.parseTIFF = exports.parseGPS = exports.parseIPTC = exports.dataToTypedArray = exports.toTypedArray = exports.isBuffer = exports.exists = exports.byteAlign = exports.dataToTypedArray = exports.dataSlice = exports.dateTimezone = exports.parseDate = exports.parseRational = exports.parseGPSDate = exports.parseGPSCoordinate = exports.parseAscii = exports.parseRational = exports.parseUndefined = exports.parseSByte = exports.parseByte = exports.parseSShort = exports.parseShort = exports.parseSLong = exports.parseLong = exports.tagNames = exports.tiffTags = exports.gpsTags = exports.exifTags = exports.iptcTags = exports.parseEXIF = exports.parseTIFF = exports.parseGPS = exports.parseIPTC = exports.parseTIFF = exports.parseGPS = exports.parseIPTC = exports.parseEXIF = exports.extractEXIF = exports.extractGPS = exports.extractIPTC = exports.extractTIFF = void 0;

        var _require = esmRequire('./utils'),
            exists = _require.exists;

        var dataToTypedArray = exports.dataToTypedArray = function dataToTypedArray(data, offset, length) {
            if (data.buffer && data.buffer.slice) {
                return new data.constructor(data.buffer.slice(offset, offset + length));
            }

            if (typeof Buffer === 'function' && Buffer.from) {
                return Buffer.from(data, offset, length);
            }

            if (typeof Uint8Array === 'function' && typeof ArrayBuffer === 'function') {
                var view = new Uint8Array(length);
                var i = -1;
                var end = offset + length;
                while (++i < length) {
                    view[i] = data[offset + i];
                }
                return view;
            }

            var copy = new Array(length);
            var i = -1;
            var end = offset + length;
            while (++i < length) {
                copy[i] = data[offset + i];
            }
            return copy;
        };

        var toTypedArray = exports.toTypedArray = function toTypedArray(data) {
            var constructor = data.constructor;
            if (constructor === Uint8Array || constructor === Uint16Array || constructor === Uint32Array || constructor === Array) {
                return data;
            }
            return new constructor(data);
        };

        var isBuffer = exports.isBuffer = function isBuffer(data) {
            return typeof Buffer !== 'undefined' && Buffer.isBuffer(data);
        };

        var exists = exports.exists = exists;

        var byteAlign = exports.byteAlign = function byteAlign(length) {
            var align = length % 4;
            return align ? 4 - align : 0;
        };

        var tagNames = exports.tagNames = {
            271: 'ImageDescription',
            272: 'Make',
            274: 'Orientation',
            305: 'Software',
            306: 'DateTime',
            315: 'Artist',
            318: 'SubsecTime',
            319: 'SubsecTimeOriginal',
            320: 'SubsecTimeDigitized',
            338: 'ColorSpace',
            34850: 'PixelFormat',
            34853: 'PixelDepth',
            37377: 'FocalLengthIn35mmFormat',
            37385: 'FocalLength',
            37386: 'FocalLength35mm',
            37396: 'FocalLengthIn35mmFormat',
            37510: 'UserComment',
            37520: 'MakerNote',
            40965: 'InteroperabilityIFD',
            41483: 'FocalPlaneXResolution',
            41484: 'FocalPlaneYResolution',
            41987: 'FocalPlaneResolutionUnit',
            41990: 'FocalPlaneXResolution',
            41991: 'FocalPlaneYResolution',
            41994: 'FocalPlaneResolutionUnit',
            53246: 'Photo3DExifTag'
        };

        var gpsTags = exports.gpsTags = {
            1: 'GPSVersionID',
            2: 'GPSLatitudeRef',
            3: 'GPSLatitude',
            4: 'GPSLongitudeRef',
            5: 'GPSLongitude',
            6: 'GPSAltitudeRef',
            7: 'GPSAltitude',
            8: 'GPSTimeStamp',
            9: 'GPSSatellites',
            10: 'GPSStatus',
            11: 'GPSDOP',
            12: 'GSPSpeedRef',
            13: 'GSPSpeed',
            14: 'GPSTrackRef',
            15: 'GPSTrack',
            16: 'GPSImgDirectionRef',
            17: 'GPSImgDirection',
            18: 'GPSDateStamp',
            23: 'GPSDifferential'
        };

        var exifTags = exports.exifTags = {
            36864: 'ExifVersion',
            36867: 'DateTimeOriginal',
            36868: 'DateTimeDigitized',
            37121: 'ComponentsConfiguration',
            37122: 'CompressedBitsPerPixel',
            37377: 'FocalLengthIn35mmFormat',
