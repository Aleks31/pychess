import unittest
import datetime
import Queue
import random

from pychess.Utils.const import WHITE
from pychess.ic import *
from pychess.ic.FICSObjects import *
from pychess.ic.FICSConnection import Connection
from pychess.ic.VerboseTelnet import PredictionsTelnet
from pychess.ic.managers.AdjournManager import AdjournManager
from pychess.ic.managers.SeekManager import SeekManager
from pychess.ic.managers.ListAndVarManager import ListAndVarManager
from pychess.ic.managers.BoardManager import BoardManager
from pychess.ic.managers.OfferManager import OfferManager
from pychess.ic.managers.HelperManager import HelperManager
from pychess.ic.managers.ErrorManager import ErrorManager
from pychess.ic.managers.FingerManager import FingerManager
from pychess.ic.managers.NewsManager import NewsManager
from pychess.ic.managers.ChatManager import ChatManager
from pychess.ic.managers.AutoLogOutManager import AutoLogOutManager
from pychess.ic.block_codes import *

class DummyConnection(Connection):
    class DummyClient(PredictionsTelnet):
        class DummyTelnet():
            def __init__(self):
                self.Q = Queue.Queue()
                self.name = "dummytelnet"
            def putline(self, line):
                self.Q.put(line)
            def write(self, text):
                pass
            def readline(self):
                return self.Q.get_nowait()
        
        def __init__(self, predictions, reply_cmd_dict):
            PredictionsTelnet.__init__(self, self.DummyTelnet(), predictions, reply_cmd_dict)
        def putline(self, line):
            self.telnet.putline(line)
    
    def __init__(self):
        Connection.__init__(self, 'host', (0,), 'tester', '123456')
        class fake_set (list):
            def __init__(self, *args):
                list.__init__(self, args)
            def add(self, x):
                self.append(x)
        self.predictions = fake_set() # make predictions able to be reordered
        self.client = self.DummyClient(self.predictions, self.reply_cmd_dict)
        self.client.setBlockModeOn()
        self.client.setLinePrefix("fics%")
    def putline(self, line):
        self.client.putline(line)
    def process_line(self):
        self.client.parse_line(self.client.get_line())
    def getUsername(self):
        return self.username
    
class DummyVarManager:
    def setVariable (self, name, value):
        pass
    def autoFlagNotify (self, *args):
        pass
    
class EmittingTestCase(unittest.TestCase):
    ''' Helps working with unittests on emitting objects.
        Warning: Strong connection to fics managers '''
    def runAndAssertEquals(self, signal, lines, expectedResults):
        self.args = None
        def handler(manager, *args): self.args = args
        self.manager.connect(signal, handler)
        random.shuffle(self.connection.client.predictions)
        
        for line in lines:
            self.connection.putline(line)
        while True:
            try:
                self.connection.process_line()
            except Queue.Empty:
                break
        
        self.assertNotEqual(self.args, None, "%s signal wasn't sent" % signal)
        self.assertEqual(self.args, expectedResults)

###############################################################################
# AdjournManager
###############################################################################

class AdjournManagerTests(EmittingTestCase):
    
    def setUp (self):
        self.connection = DummyConnection()
        self.connection.players = FICSPlayers(self.connection)
        self.connection.games = FICSGames(self.connection)
        self.connection.lvm = DummyVarManager()
        self.connection.em = ErrorManager(self.connection)
        self.connection.glm = SeekManager(self.connection)
        self.connection.bm = BoardManager(self.connection)
        self.connection.fm = FingerManager(self.connection)
        self.connection.nm = NewsManager(self.connection)
        self.connection.om = OfferManager(self.connection)
        self.connection.cm = ChatManager(self.connection)
        self.connection.alm = AutoLogOutManager(self.connection)
        self.connection.adm = AdjournManager(self.connection)
        self.connection.bm.start()
        self.connection.players.start()
        self.connection.games.start()
        self.manager = self.connection.adm
        
    def test1(self):
        """Testing an advanced line"""
        
        signal = 'onAdjournmentsList'
        
        lines = ['    C Opponent       On Type          Str  M    ECO Date',
            ' 1: W gbtami         N [ wr  2   2] 31-31 W18  --- Wed Dec 23, 06:58 PST 2009',
            'fics% ']
        
        gametime = datetime.datetime(2009, 12, 23, 6, 58)
        us = self.connection.players.get(FICSPlayer(self.connection.getUsername()))
        gbtami = self.connection.players.get(FICSPlayer('gbtami'))
        game = FICSAdjournedGame(us, gbtami, our_color=WHITE, length=34,
            time=gametime, rated=True, game_type=GAME_TYPES_BY_FICS_NAME['wild'],
            private=False, min=2, inc=2)
        expectedResult = [ game ]
        
        self.runAndAssertEquals(signal, lines, (expectedResult,))
    
    def test2(self):
        """Testing a double line"""
        
        signal = 'onAdjournmentsList'
        
        lines = ['    C Opponent       On Type          Str  M    ECO Date',
                 ' 1: W TheDane       N [ br  2  12]  0-0  B2   ??? Sun Nov 23,  6:14 CST 1997',
                 ' 2: W PyChess       Y [psu  2  12] 39-39 W3   C20 Sun Jan 11, 17:40 ??? 2009',
                 'fics% ']
        
        gametime1 = datetime.datetime(1997, 11, 23, 6, 14)
        gametime2 = datetime.datetime(2009, 1, 11, 17, 40)
        game1 = FICSAdjournedGame(FICSPlayer(self.connection.getUsername()),
            FICSPlayer('TheDane'), our_color=WHITE, length=3, time=gametime1,
            rated=True, game_type=GAME_TYPES['blitz'], private=False, min=2, inc=12)
        game2 = FICSAdjournedGame(FICSPlayer(self.connection.getUsername()),
            FICSPlayer('PyChess'), our_color=WHITE, length=4, time=gametime2,
            rated=False, game_type=GAME_TYPES['standard'], private=True, min=2, inc=12)

        expectedResult = [ game1, game2 ]        
        self.runAndAssertEquals(signal, lines, (expectedResult,))
    
    def test3(self):
        """ The case where player has no games in adjourned """
        
        self.runAndAssertEquals('onAdjournmentsList',
            ['%s has no adjourned games.' % self.connection.username], ([],))
    
    def test4(self):
        """ Test acquiring preview without adjournment list """
        
        signal = 'adjournedGamePreview'
        
        lines = ['BwanaSlei (1137) vs. mgatto (1336) --- Wed Nov  5, 20:56 PST 2008',
                 'Rated blitz match, initial time: 5 minutes, increment: 0 seconds.',
                 '',
                 'Move  BwanaSlei               mgatto',
                 '----  ---------------------   ---------------------',
                 '  1.  e4      (0:00.000)     c5      (0:00.000)',  
                 '  2.  Nf3     (0:00.000) ',
                 '      {White lost connection; game adjourned} *',
                 'fics% ']
        
        expectedPgn = '[Event "FICS rated blitz game"]\n[Site "FICS"]\n[White "BwanaSlei"]\n' \
                      '[Black "mgatto"]\n[TimeControl "300+0"]\n[Result "*"]\n' \
                      '[WhiteClock "0:05:00.000"]\n[BlackClock "0:05:00.000"]\n' \
                      '[WhiteElo "1137"]\n[BlackElo "1336"]\n[Year "2008"]\n' \
                      '[Month "11"]\n[Day "5"]\n[Time "20:56:00"]\n'
        expectedPgn += '1. e4 c5 2. Nf3 *\n'
        game = FICSAdjournedGame(FICSPlayer("BwanaSlei"), FICSPlayer("mgatto"),
            rated=True, game_type=GAME_TYPES["blitz"], min=5, inc=0,
            board=FICSBoard(300000, 300000, expectedPgn), reason=11)
        game.wplayer.addRating(TYPE_BLITZ, 1137)
        game.bplayer.addRating(TYPE_BLITZ, 1336)
        expectedResults = (game,)
        
        self.runAndAssertEquals(signal, lines, expectedResults)
    
    def test5(self):
        """ Test acquiring preview with adjournment list """
        
        signal = 'adjournedGamePreview'
        
        lines = ['C Opponent       On Type          Str  M    ECO Date',
                 '1: W BabyLurking     Y [ br  5   0] 29-13 W27  D37 Fri Nov  5, 04:41 PDT 2010',
                 '',
                 'mgatto (1233) vs. BabyLurking (1455) --- Fri Nov  5, 04:33 PDT 2010',
                 'Rated blitz match, initial time: 5 minutes, increment: 0 seconds.',
                 '',
                 'Move  mgatto             BabyLurking',
                 '----  ----------------   ----------------',
                 '1.  Nf3     (0:00)     d5      (0:00)',
                 '2.  d4      (0:03)     Nf6     (0:00)',
                 '3.  c4      (0:03)     e6      (0:00)',
                 '    {Game adjourned by mutual agreement} *']
        
        expectedPgn = '[Event "FICS rated blitz game"]\n[Site "FICS"]\n[White "mgatto"]\n' \
                      '[Black "BabyLurking"]\n[TimeControl "300+0"]\n[Result "*"]\n' \
                      '[WhiteClock "0:04:54.000"]\n[BlackClock "0:05:00.000"]\n' \
                      '[WhiteElo "1233"]\n[BlackElo "1455"]\n[Year "2010"]\n[Month "11"]' \
                      '\n[Day "5"]\n[Time "04:33:00"]\n1. Nf3 d5 2. d4 Nf6 3. c4 e6 *\n'
        game = FICSAdjournedGame(FICSPlayer("mgatto"), FICSPlayer("BabyLurking"),
            rated=True, game_type=GAME_TYPES["blitz"], min=5, inc=0,
            board=FICSBoard(294000, 300000, expectedPgn), reason=6)
        game.wplayer.addRating(TYPE_BLITZ, 1233)
        game.bplayer.addRating(TYPE_BLITZ, 1455)
        expectedResults = (game,)
        self.runAndAssertEquals(signal, lines, expectedResults)

###############################################################################
# SeekManager
###############################################################################

class SeekManagerTests(EmittingTestCase):
    
    def setUp (self):
        self.connection = DummyConnection()
        # The real one stucks
        #self.connection.lvm = ListAndVarManager(self.connection)
        self.connection.lvm = DummyVarManager()
        self.connection.glm = SeekManager(self.connection)
        self.connection.bm = BoardManager(self.connection)
        self.manager = self.connection.glm
    
    def test1 (self):
        """ Seek add """
        
        signal = 'addSeek'
        
        lines = ['<s> 10 w=warbly ti=00 rt=1291  t=3 i=0 r=r tp=blitz c=? rr=1200-1400 a=t f=t']
        expectedResult = {'gameno':'10', 'gametype': GAME_TYPES["blitz"],
            'rmin':1200, 'rmax':1400, 'cp':False, 'rt':'1291', 'manual':False,
            'color':None, 'title': '', 'w':'warbly', 'r':'r', 't':'3', 'i':'0'}
        self.runAndAssertEquals(signal, lines, (expectedResult,))
        
        lines = ['<s> 124 w=leaderbeans ti=02 rt=1637E t=3 i=0 r=u tp=blitz c=B rr=0-9999 a=t f=f']
        expectedResult = {'gameno':'124', 'gametype': GAME_TYPES["blitz"],
            'rmin':0, 'rmax':9999, 'cp':True, 'rt':'1637', 'manual':False,
            'color':'black', 'title': '(C)', 'w':'leaderbeans', 'r':'u', 't':'3', 'i':'0'}
        self.runAndAssertEquals(signal, lines, (expectedResult,))

        lines = ['<s> 14 w=microknight ti=00 rt=1294  t=15 i=0 r=u tp=standard c=? rr=1100-1450 a=f f=f']
        expectedResult = {'gameno':'14', 'gametype': GAME_TYPES["standard"],
            'rmin':1100, 'rmax':1450, 'cp':False, 'rt':'1294', 'manual':True,
            'color':None, 'title': '', 'w':'microknight', 'r':'u', 't':'15', 'i':'0'}
        self.runAndAssertEquals(signal, lines, (expectedResult,))
    
    def test2 (self):
        """ Seek clear """
        self.runAndAssertEquals('clearSeeks', ['<sc>'], ())
    
    def test3 (self):
        """ Seek remove """
        lines = ['<s> 124 w=leaderbeans ti=02 rt=1637E t=3 i=0 r=u tp=blitz c=B rr=0-9999 a=t f=f',
                 '<sr> 124', '']
        self.runAndAssertEquals('removeSeek', lines, ('124',))
    
    def test4 (self):
        """ Seek add resulting from a seek command reply """
        
        lines = [BLOCK_START + '54' + BLOCK_SEPARATOR + '155' + BLOCK_SEPARATOR,
                 '<sn> 121 w=mgatto ti=00 rt=1677  t=6 i=1 r=r tp=wild/4 c=? rr=0-9999 a=f f=f',
                 'fics% Your seek has been posted with index 121.',
                 '(9 player(s) saw the seek.)',
                 BLOCK_END]
        expectedResult = {'gameno':'121', 'gametype': GAME_TYPES["wild/4"],
            'rmin':0, 'rmax':9999, 'cp':False, 'rt':'1677', 'manual':True,
            'color':None, 'title': '', 'w':'mgatto', 'r':'r', 't':'6', 'i':'1'}
        self.runAndAssertEquals('addSeek', lines, (expectedResult,))
    
    def test5 (self):
        """ Confirm that seeks remove resulting from an unseek command reply
            is caught by our_seeks_removed rather than on_seek_remove
        """
        
        signal = 'our_seeks_removed'
        
        lines = [BLOCK_START + '54' + BLOCK_SEPARATOR + '156' + BLOCK_SEPARATOR,
                 "<sr> 8 17 30",
                 "Your seeks have been removed.",
                 BLOCK_END]
        self.runAndAssertEquals('our_seeks_removed', lines, ())

    def test6 (self):
        lines = [BLOCK_START + '62' + BLOCK_SEPARATOR + '155' + BLOCK_SEPARATOR +
                 "Updating seek ad 105 to automatic.",
                 "",
                 "<sr> 105",
                 "",
                 "<sn> 105 w=mgatto ti=00 rt=1651  t=3 i=0 r=r tp=wild/4 c=? rr=1375-1925 a=t f=f",
                 "Your seek has been posted with index 105.",
                 "(2 player(s) saw the seek.)",
                 BLOCK_END]
        self.runAndAssertEquals('seek_updated', lines, ('to automatic',))
    
    def test7 (self):
        lines = [BLOCK_START + '62' + BLOCK_SEPARATOR + '155' + BLOCK_SEPARATOR +
                 "Updating seek ad 12 to manual.",
                 "Updating seek ad 12; rating range now 0-9999.",
                 "",
                 "<sr> 12",
                 "",
                 "<sn> 12 w=mgatto ti=00 rt=1640  t=3 i=0 r=r tp=wild/4 c=? rr=0-9999 a=f f=f",
                 "Your seek has been posted with index 12.",
                 "(11 player(s) saw the seek.)",
                 BLOCK_END]
        self.runAndAssertEquals('seek_updated', lines, ('to manual; rating range now 0-9999',))

class BoardManagerTests(EmittingTestCase):
    
    def setUp (self):
        self.connection = DummyConnection()
        self.connection.players = FICSPlayers(self.connection)
        self.connection.games = FICSGames(self.connection)
        self.connection.lvm = DummyVarManager()
        self.connection.em = ErrorManager(self.connection)
        self.connection.glm = SeekManager(self.connection)
        self.connection.bm = BoardManager(self.connection)
        self.connection.fm = FingerManager(self.connection)
        self.connection.nm = NewsManager(self.connection)
        self.connection.om = OfferManager(self.connection)
        self.connection.cm = ChatManager(self.connection)
        self.connection.alm = AutoLogOutManager(self.connection)
        self.connection.adm = AdjournManager(self.connection)
        self.connection.bm.start()
        self.connection.players.start()
        self.connection.games.start()
        self.manager = self.connection.bm
    
    def test1 (self):
        lines = [BLOCK_START + '110' + BLOCK_SEPARATOR + '155' + BLOCK_SEPARATOR,
                 "Your seek matches one already posted by Thegermain.",
                 "",
                 "<sr> 111 25",
                 "fics%" ,
                 "<sr> 153",
                 "fics%" ,
                 "Creating: mgatto (1327) Thegermain (1645) unrated blitz 4 0",
                 "{Game 55 (mgatto vs. Thegermain) Creating unrated blitz match.}",
                 "",
                 "<12> rnbqkbnr pppppppp -------- -------- -------- -------- PPPPPPPP RNBQKBNR W -1 1 1 1 1 0 55 mgatto Thegermain 1 4 0 39 39 240000 240000 1 none (0:00.000) none 0 0 0",
                 BLOCK_END]
        me = self.connection.players.get(FICSPlayer('mgatto'))
        me.addRating(TYPE_BLITZ, 1327)
        opponent = self.connection.players.get(FICSPlayer('Thegermain'))
        opponent.addRating(TYPE_BLITZ, 1645)
        game = FICSGame(me, opponent, gameno=55, rated=False,
            game_type=GAME_TYPES['blitz'], private=False, min=4, inc=0,
            board=FICSBoard(240000, 240000, fen=FEN_START))
        me.game = game
        opponent.game = game
        self.runAndAssertEquals("playGameCreated", lines, (game,))
    
    def test2 (self):
        lines = [BLOCK_START + '111' + BLOCK_SEPARATOR + '155' + BLOCK_SEPARATOR,
                 "Your seek matches one already posted by GuestRLJC.",
                 "",
                 "<sr> 135",
                 "fics%" ,
                 "Creating: mgatto (1305) GuestRLJC (++++) unrated blitz 5 0",
                 "{Game 442 (mgatto vs. GuestRLJC) Creating unrated blitz match.}",
                 "",
                 "<12> rnbqkbnr pppppppp -------- -------- -------- -------- PPPPPPPP RNBQKBNR W -1 1 1 1 1 0 442 mgatto GuestRLJC 1 5 0 39 39 300000 300000 1 none (0:00.000) none 0 0 0",
                 BLOCK_END]
        me = self.connection.players.get(FICSPlayer('mgatto'))
        me.addRating(TYPE_BLITZ, 1305)
        opponent = self.connection.players.get(FICSPlayer('GuestRLJC'))
        game = FICSGame(me, opponent, gameno=442, rated=False,
            game_type=GAME_TYPES['blitz'], private=False, min=5, inc=0,
            board=FICSBoard(300000, 300000, fen=FEN_START))
        me.game = game
        opponent.game = game
        self.runAndAssertEquals("playGameCreated", lines, (game,))
        
###############################################################################
# OfferManager
###############################################################################

class OfferManagerTests(EmittingTestCase):
    
    def setUp (self):
        self.connection = DummyConnection()
        # The real one stucks
        #self.connection.lvm = ListAndVarManager(self.connection)
        self.connection.lvm = DummyVarManager()
        self.manager = OfferManager(self.connection)
    
    def test1 (self):
        """ Challenges """
        signal = 'onChallengeAdd'
        
        lines = ['<pf> 59 w=antiseptic t=match p=antiseptic (1945) mgatto (1729) rated wild 6 1 Loaded from wild/4 (adjourned)']
        expectedResult = {'gametype': GAME_TYPES["wild/4"], "w": 'antiseptic',
                "rt": '1945', "r": 'r', "t": "6", "i": "1", "color": None,
                "is_adjourned": True}
        self.runAndAssertEquals(signal, lines, ('59', expectedResult,))
        
        lines = ['<pf> 71 w=joseph t=match p=joseph (1632) mgatto (1742) rated wild 5 1 Loaded from wild/fr (adjourned)']
        expectedResult = {'gametype': GAME_TYPES["wild/fr"], "w": 'joseph',
                "rt": '1632', "r": 'r', "t": "5", "i": "1", "color": None,
                "is_adjourned": True}
        self.runAndAssertEquals(signal, lines, ('71', expectedResult,))

        lines = ['<pf> 45 w=GuestGYXR t=match p=GuestGYXR (----) Lobais (----) unrated losers 2 12']
        expectedResult = {'gametype': GAME_TYPES["losers"], "w": 'GuestGYXR',
                "rt": '0', "r": 'u', "t": "2", "i": "12", "color": None,
                "is_adjourned": False}
        self.runAndAssertEquals(signal, lines, ('45', expectedResult,))

        lines = ['<pf> 39 w=GuestDVXV t=match p=GuestDVXV (----) GuestNXMP (----) unrated blitz 2 12 (adjourned)']
        expectedResult = {'gametype': GAME_TYPES["blitz"], "w": 'GuestDVXV',
                "rt": '0', "r": 'u', "t": "2", "i": "12", "color": None,
                "is_adjourned": True}
        self.runAndAssertEquals(signal, lines, ('39', expectedResult,))

        lines = ['<pf> 20 w=GuestFQPB t=match p=GuestFQPB (----) [white] mgatto (1322) unrated blitz 2 12']
        expectedResult = {'gametype': GAME_TYPES["blitz"], "w": 'GuestFQPB',
                "rt": '0', "r": 'u', "t": "2", "i": "12", "color": "white",
                "is_adjourned": False}
        self.runAndAssertEquals(signal, lines, ('20', expectedResult,))

        lines = ['<pf> 7 w=GuestFQPB t=match p=GuestFQPB (----) [black] mgatto (----) unrated untimed']
        expectedResult = {'gametype': GAME_TYPES["untimed"], "w": 'GuestFQPB',
                "rt": '0', "r": 'u', "t": "0", "i": "0", "color": "black",
                "is_adjourned": False}
        self.runAndAssertEquals(signal, lines, ('7', expectedResult,))

if __name__ == '__main__':
    unittest.main()
