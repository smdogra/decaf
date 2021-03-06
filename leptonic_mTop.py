#!/usr/bin/env python
import lz4.frame as lz4f
import cloudpickle
import json
import pprint
import numpy as np
import awkward
np.seterr(divide='ignore', invalid='ignore', over='ignore')
from coffea.arrays import Initialize
from coffea import hist, processor
from coffea.util import load, save
from coffea.jetmet_tools import FactorizedJetCorrector, JetCorrectionUncertainty, JetTransformer, JetResolution, JetResolutionScaleFactor
from optparse import OptionParser
from uproot_methods import TVector2Array, TLorentzVectorArray

class AnalysisProcessor(processor.ProcessorABC):

    lumis = { #Values from https://twiki.cern.ch/twiki/bin/viewauth/CMS/PdmVAnalysisSummaryTable                                                      
        '2016': 35.92,
        '2017': 41.53,
        '2018': 59.74
    }

    met_filter_flags = {
     
        '2016': ['goodVertices',
                 'globalSuperTightHalo2016Filter',
                 'HBHENoiseFilter',
                 'HBHENoiseIsoFilter',
                 'EcalDeadCellTriggerPrimitiveFilter',
                 'BadPFMuonFilter'
             ],

        '2017': ['goodVertices',
                 'globalSuperTightHalo2016Filter',
                 'HBHENoiseFilter',
                 'HBHENoiseIsoFilter',
                 'EcalDeadCellTriggerPrimitiveFilter',
                 'BadPFMuonFilter'
             ],

        '2018': ['goodVertices',
                 'globalSuperTightHalo2016Filter',
                 'HBHENoiseFilter',
                 'HBHENoiseIsoFilter',
                 'EcalDeadCellTriggerPrimitiveFilter',
                 'BadPFMuonFilter'
             ]
    }

            
    def __init__(self, year, xsec, corrections, ids, common):

        self._columns = """                                                                                                                    
        MET_pt
        MET_phi
        CaloMET_pt
        CaloMET_phi
        Electron_pt
        Electron_eta
        Electron_phi
        Electron_mass
        Muon_pt
        Muon_eta
        Muon_phi
        Muon_mass
        Tau_pt
        Tau_eta
        Tau_phi
        Tau_mass
        Photon_pt
        Photon_eta
        Photon_phi
        Photon_mass
        Jet_pt
        Jet_eta
        Jet_phi
        Jet_mass
        Jet_btagDeepB
        Jet_btagDeepFlavB
        GenPart_pt
        GenPart_eta
        GenPart_phi
        GenPart_mass
        GenPart_pdgId
        GenPart_status
        GenPart_statusFlags
        GenPart_genPartIdxMother
        PV_npvs
        Electron_cutBased
        Electron_dxy
        Electron_dz
        Muon_pfRelIso04_all
        Muon_tightId
        Muon_mediumId
        Muon_dxy
        Muon_dz
        Tau_idMVAoldDM2017v2
        Tau_idDecayMode
        Photon_cutBased
        Photon_electronVeto
        Photon_cutBasedBitmap
        Jet_jetId
        Jet_neHEF
        Jet_neEmEF
        Jet_chHEF
        Jet_chEmEF
        genWeight
        """.split()
        
        self._year = year

        self._lumi = 1000.*float(AnalysisProcessor.lumis[year])

        self._xsec = xsec
        #Need Help from Matteo/Dough for samples
        self._samples = {
            'sre':('WJets','DY','TT','ST','WW','WZ','ZZ','QCD','SingleElectron'),
            'srm':('WJets','DY','TT','ST','WW','WZ','ZZ','QCD','SingleMuon'),
            'ttbare':('WJets','DY','TT','ST','WW','WZ','ZZ','QCD', 'SingleElectron'),
            'ttbarm':('WJets','DY','TT','ST','WW','WZ','ZZ','QCD', 'SingleMuon'),
            'wjete':('WJets','DY','TT','ST','WW','WZ','ZZ','QCD', 'SingleElectron'),
            'wjetm':('WJets','DY','TT','ST','WW','WZ','ZZ','QCD', 'SingleMuon'),
            'dilepe':'DY','TT','ST','WW','WZ','ZZ','SingleElectron'),
            'dilepm':'DY','TT','ST','WW','WZ','ZZ','SingleMuon')

        }

        self._met_triggers = {
            '2016': [
                'PFMETNoMu120_PFMHTNoMu120_IDTight'
            ],
            '2017': [
                'PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60',
                'PFMETNoMu120_PFMHTNoMu120_IDTight'
            ],
            '2018': [
                'PFMETNoMu120_PFMHTNoMu120_IDTight_PFHT60',
                'PFMETNoMu120_PFMHTNoMu120_IDTight'
            ]
        }

        self._singlephoton_triggers = {
            '2016': [
                'Photon175',
                'Photon165_HE10'
            ],
            '2017': [
                'Photon200'
            ],
            '2018': [
                'Photon200'
            ]
        }

        self._singleelectron_triggers = {
            '2016': [
                'Ele27_WPTight_Gsf',
                'Ele115_CaloIdVT_GsfTrkIdT',
                'Photon175'
            ],
            '2017': [
                #'Ele35_WPTight_Gsf',
                'Ele32_WPTight_Gsf',
                'Ele115_CaloIdVT_GsfTrkIdT',
                'Photon200'
            ],
            '2018': [
                'Ele32_WPTight_Gsf',
                'Ele115_CaloIdVT_GsfTrkIdT',
                'Photon200'
            ]
        }

        self._singlemuon_triggers = {
            '2016': [
                 'IsoMu24',
                 'IsoTkMu24',
                 'Mu50',
                 'TkMu50'

            ],
            '2017': [
                'IsoMu27',
                'Mu50',
                'OldMu100',
                'TkMu100'
            ],
            '2018': [
                'IsoMu24',
                'Mu50',
                'OldMu100',
                'TkMu100'
            ]
        }

        self._jec = {
        
            '2016': [
                'Summer16_07Aug2017_V11_MC_L1FastJet_AK4PFPuppi',
                'Summer16_07Aug2017_V11_MC_L2L3Residual_AK4PFPuppi',
                'Summer16_07Aug2017_V11_MC_L2Relative_AK4PFPuppi',
                'Summer16_07Aug2017_V11_MC_L2Residual_AK4PFPuppi',
                'Summer16_07Aug2017_V11_MC_L3Absolute_AK4PFPuppi'
            ],
            
            '2017':[
                'Fall17_17Nov2017_V32_MC_L1FastJet_AK4PFPuppi',
                'Fall17_17Nov2017_V32_MC_L2L3Residual_AK4PFPuppi',
                'Fall17_17Nov2017_V32_MC_L2Relative_AK4PFPuppi',
                'Fall17_17Nov2017_V32_MC_L2Residual_AK4PFPuppi',
                'Fall17_17Nov2017_V32_MC_L3Absolute_AK4PFPuppi'
            ],

            '2018':[
                'Autumn18_V19_MC_L1FastJet_AK4PFPuppi',
                'Autumn18_V19_MC_L2L3Residual_AK4PFPuppi',
                'Autumn18_V19_MC_L2Relative_AK4PFPuppi', #currently broken
                'Autumn18_V19_MC_L2Residual_AK4PFPuppi',  
                'Autumn18_V19_MC_L3Absolute_AK4PFPuppi'  
            ]
        }

        self._junc = {
    
            '2016':[
                'Summer16_07Aug2017_V11_MC_Uncertainty_AK4PFPuppi'
            ],

            '2017':[
                'Fall17_17Nov2017_V32_MC_Uncertainty_AK4PFPuppi'
            ],

            '2018':[
                'Autumn18_V19_MC_Uncertainty_AK4PFPuppi'
            ]
        }

        self._jr = {
        
            '2016': [
                'Summer16_25nsV1b_MC_PtResolution_AK4PFPuppi'
            ],
        
            '2017':[
                'Fall17_V3b_MC_PtResolution_AK4PFPuppi'
            ],

            '2018':[
                'Autumn18_V7b_MC_PtResolution_AK4PFPuppi'
            ]
        }

        self._jersf = {
    
            '2016':[
                'Summer16_25nsV1b_MC_SF_AK4PFPuppi'
            ],

            '2017':[
                'Fall17_V3b_MC_SF_AK4PFPuppi'
            ],

            '2018':[
                'Autumn18_V7b_MC_SF_AK4PFPuppi'
            ]
        }

        self._corrections = corrections
        self._ids = ids
        self._common = common

        self._accumulator = processor.dict_accumulator({
            'sumw': hist.Hist(
                'sumw', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Bin('sumw', 'Weight value', [0.])
            ),
            'CaloMinusPfOverRecoil': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('CaloMinusPfOverRecoil','Calo - Pf / Recoil',35,0,1)
            ),
            'recoil': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'),
                hist.Bin('recoil','Hadronic Recoil',[250.0, 280.0, 310.0, 340.0, 370.0, 400.0, 430.0, 470.0, 510.0, 550.0, 590.0, 640.0, 690.0, 740.0, 790.0, 840.0, 900.0, 960.0, 1020.0, 1090.0, 1160.0, 1250.0])
            ),
            'met': hist.Hist(
            'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Cat('region', 'Region'),
                hist.Cat('systematic', 'Systematic'),
                hist.Bin('met','MET',30,0,600)
            ),
            'mindphi': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('mindphi','Min dPhi(MET,AK4s)',30,0,3.5)
            ),
            'j1pt': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('j1pt','AK4 Leading Jet Pt',[30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 250.0, 280.0, 310.0, 340.0, 370.0, 400.0, 430.0, 470.0, 510.0, 550.0, 590.0, 640.0, 690.0, 740.0, 790.0, 840.0, 900.0, 960.0, 1020.0, 1090.0, 1160.0, 1250.0])
            ),
            'j1eta': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('j1eta','AK4 Leading Jet Eta',35,-3.5,3.5)
            ),
            'j1phi': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('j1phi','AK4 Leading Jet Phi',35,-3.5,3.5)
            ),
            'njets': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('njets','AK4 Number of Jets',6,-0.5,5.5)
            ),
            'ndcsvL': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('ndcsvL','AK4 Number of deepCSV Loose Jets',6,-0.5,5.5)
            ),
            'ndflvL': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('ndflvL','AK4 Number of deepFlavor Loose Jets',6,-0.5,5.5)
            ),
            'e1pt': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('e1pt','Leading Electron Pt',[30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 250.0, 280.0, 310.0, 340.0, 370.0, 400.0, 430.0, 470.0, 510.0, 550.0, 590.0, 640.0, 690.0, 740.0, 790.0, 840.0, 900.0, 960.0, 1020.0, 1090.0, 1160.0, 1250.0])
            ),
            'e1eta': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('e1eta','Leading Electron Eta',48,-2.4,2.4)
            ),
            'e1phi': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('e1phi','Leading Electron Phi',64,-3.2,3.2)
            ),
            'dielemass': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('dielemass','Dielectron mass',100,0,500)
            ),
            'dielept': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Cat('region', 'Region'),
                hist.Cat('systematic', 'Systematic'),
                hist.Bin('dielept','Dielectron Pt',150,0,800)
            ),
            'mu1pt': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('mu1pt','Leading Muon Pt',[30.0, 60.0, 90.0, 120.0, 150.0, 180.0, 210.0, 250.0, 280.0, 310.0, 340.0, 370.0, 400.0, 430.0, 470.0, 510.0, 550.0, 590.0, 640.0, 690.0, 740.0, 790.0, 840.0, 900.0, 960.0, 1020.0, 1090.0, 1160.0, 1250.0])
            ),
            'mu1eta': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('mu1eta','Leading Muon Eta',48,-2.4,2.4)
            ),
            'mu1phi': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('mu1phi','Leading Muon Phi',64,-3.2,3.2)
            ),
            'dimumass': hist.Hist(
                'Events', 
                hist.Cat('dataset', 'Dataset'), 
                hist.Cat('region', 'Region'), 
                hist.Cat('systematic', 'Systematic'), 
                hist.Bin('dimumass','Dimuon mass',100,0,500)
            ),
            'dimupt': hist.Hist(
                'Events',
                hist.Cat('dataset', 'Dataset'),
                hist.Cat('region', 'Region'),
                hist.Cat('systematic', 'Systematic'),
                hist.Bin('dimupt','Dimuon Pt',150,0,800)
            ),
        })

    @property
    def accumulator(self):
        return self._accumulator

    @property
    def columns(self):
        return self._columns

    def process(self, events):

        dataset = events.metadata['dataset']

        selected_regions = []
        for region, samples in self._samples.items():
            for sample in samples:
                if sample not in dataset: continue
                selected_regions.append(region)

        isData = 'genWeight' not in events.columns
        selection = processor.PackedSelection()
        weights = {}
        hout = self.accumulator.identity()

        ###
        #Getting corrections, ids from .coffea files
        ###   Sunil Need to check  why we need corrections

        #get_msd_weight          = self._corrections['get_msd_weight']
        get_ttbar_weight        = self._corrections['get_ttbar_weight']
        get_nlo_weight          = self._corrections['get_nlo_weight'][self._year]         
        get_nnlo_weight         = self._corrections['get_nnlo_weight']
        get_nnlo_nlo_weight     = self._corrections['get_nnlo_nlo_weight']
        get_adhoc_weight        = self._corrections['get_adhoc_weight']
        get_pu_weight           = self._corrections['get_pu_weight'][self._year]          
        get_met_trig_weight     = self._corrections['get_met_trig_weight'][self._year]    
        get_met_zmm_trig_weight = self._corrections['get_met_zmm_trig_weight'][self._year]
        get_ele_trig_weight     = self._corrections['get_ele_trig_weight'][self._year]    
        get_pho_trig_weight     = self._corrections['get_pho_trig_weight'][self._year]    
        get_ele_loose_id_sf     = self._corrections['get_ele_loose_id_sf'][self._year]
        get_ele_tight_id_sf     = self._corrections['get_ele_tight_id_sf'][self._year]
        get_ele_loose_id_eff    = self._corrections['get_ele_loose_id_eff'][self._year]
        get_ele_tight_id_eff    = self._corrections['get_ele_tight_id_eff'][self._year]
        get_pho_tight_id_sf     = self._corrections['get_pho_tight_id_sf'][self._year]
        get_mu_tight_id_sf      = self._corrections['get_mu_tight_id_sf'][self._year]
        get_mu_loose_id_sf      = self._corrections['get_mu_loose_id_sf'][self._year]
        get_ele_reco_sf         = self._corrections['get_ele_reco_sf'][self._year]
        get_mu_tight_iso_sf     = self._corrections['get_mu_tight_iso_sf'][self._year]
        get_mu_loose_iso_sf     = self._corrections['get_mu_loose_iso_sf'][self._year]
        get_ecal_bad_calib      = self._corrections['get_ecal_bad_calib']
        get_deepflav_weight     = self._corrections['get_btag_weight']['deepflav'][self._year]
        Jetevaluator            = self._corrections['Jetevaluator']
        
        isLooseElectron = self._ids['isLooseElectron'] 
        isTightElectron = self._ids['isTightElectron'] 
        isLooseMuon     = self._ids['isLooseMuon']     
        isTightMuon     = self._ids['isTightMuon']     
        isLooseTau      = self._ids['isLooseTau']      
        isLoosePhoton   = self._ids['isLoosePhoton']   
        isTightPhoton   = self._ids['isTightPhoton']   
        isGoodJet       = self._ids['isGoodJet']       
        #isGoodFatJet    = self._ids['isGoodFatJet']    
        isHEMJet        = self._ids['isHEMJet']        
        
        match = self._common['match']
        deepflavWPs = self._common['btagWPs']['deepflav'][self._year]
        deepcsvWPs = self._common['btagWPs']['deepcsv'][self._year]

        ###
        # Derive jet corrector for JEC/JER
        ###
        
        JECcorrector = FactorizedJetCorrector(**{name: Jetevaluator[name] for name in self._jec[self._year]})
        JECuncertainties = JetCorrectionUncertainty(**{name:Jetevaluator[name] for name in self._junc[self._year]})
        JER = JetResolution(**{name:Jetevaluator[name] for name in self._jr[self._year]})
        JERsf = JetResolutionScaleFactor(**{name:Jetevaluator[name] for name in self._jersf[self._year]})
        Jet_transformer = JetTransformer(jec=JECcorrector,junc=JECuncertainties, jer = JER, jersf = JERsf)
        
        ###
        #Initialize global quantities (MET ecc.)
        ###

        met = events.MET
        met['T']  = TVector2Array.from_polar(met.pt, met.phi)
        met['p4'] = TLorentzVectorArray.from_ptetaphim(met.pt, 0., met.phi, 0.)
        calomet = events.CaloMET

        ###
        #Initialize physics objects
        ###

        e = events.Electron
        e['isloose'] = isLooseElectron(e.pt,e.eta,e.dxy,e.dz,e.cutBased,self._year)
        e['istight'] = isTightElectron(e.pt,e.eta,e.dxy,e.dz,e.cutBased,self._year)
        e['T'] = TVector2Array.from_polar(e.pt, e.phi)
        #e['p4'] = TLorentzVectorArray.from_ptetaphim(e.pt, e.eta, e.phi, e.mass)
        e_loose = e[e.isloose.astype(np.bool)]
        e_tight = e[e.istight.astype(np.bool)]
        e_ntot = e.counts
        e_nloose = e_loose.counts
        e_ntight = e_tight.counts
        leading_e = e[e.pt.argmax()]
        leading_e = leading_e[leading_e.istight.astype(np.bool)]

        mu = events.Muon
        mu['isloose'] = isLooseMuon(mu.pt,mu.eta,mu.pfRelIso04_all,mu.looseId,self._year)
        mu['istight'] = isTightMuon(mu.pt,mu.eta,mu.pfRelIso04_all,mu.tightId,self._year)
        mu['T'] = TVector2Array.from_polar(mu.pt, mu.phi)
        #mu['p4'] = TLorentzVectorArray.from_ptetaphim(mu.pt, mu.eta, mu.phi, mu.mass)
        mu_loose=mu[mu.isloose.astype(np.bool)]
        mu_tight=mu[mu.istight.astype(np.bool)]
        mu_ntot = mu.counts
        mu_nloose = mu_loose.counts
        mu_ntight = mu_tight.counts
        leading_mu = mu[mu.pt.argmax()]
        leading_mu = leading_mu[leading_mu.istight.astype(np.bool)]

        tau = events.Tau
        tau['isclean']=~match(tau,mu_loose,0.5)&~match(tau,e_loose,0.5)
        tau['isloose']=isLooseTau(tau.pt,tau.eta,tau.idDecayMode,tau.idMVAoldDM2017v2,self._year)
        tau_clean=tau[tau.isclean.astype(np.bool)]
        tau_loose=tau_clean[tau_clean.isloose.astype(np.bool)]
        tau_ntot=tau.counts
        tau_nloose=tau_loose.counts

        pho = events.Photon
        pho['isclean']=~match(pho,mu_loose,0.5)&~match(pho,e_loose,0.5)
        _id = 'cutBasedBitmap'
        if self._year=='2016': _id = 'cutBased'
        pho['isloose']=isLoosePhoton(pho.pt,pho.eta,pho[_id],self._year)
        pho['istight']=isTightPhoton(pho.pt,pho.eta,pho[_id],self._year)
        pho['T'] = TVector2Array.from_polar(pho.pt, pho.phi)
        #pho['p4'] = TLorentzVectorArray.from_ptetaphim(pho.pt, pho.eta, pho.phi, pho.mass)
        pho_clean=pho[pho.isclean.astype(np.bool)]
        pho_loose=pho_clean[pho_clean.isloose.astype(np.bool)]
        pho_tight=pho_clean[pho_clean.istight.astype(np.bool)]
        pho_ntot=pho.counts
        pho_nloose=pho_loose.counts
        pho_ntight=pho_tight.counts
        leading_pho = pho[pho.pt.argmax()]
        leading_pho = leading_pho[leading_pho.isclean.astype(np.bool)]
        leading_pho = leading_pho[leading_pho.istight.astype(np.bool)]

        j = events.Jet
        j['isgood'] = isGoodJet(j.pt, j.eta, j.jetId, j.neHEF, j.neEmEF, j.chHEF, j.chEmEF)
        j['isHEM'] = isHEMJet(j.pt, j.eta, j.phi)
        j['isclean'] = ~match(j,e_loose,0.4)&~match(j,mu_loose,0.4)&~match(j,pho_loose,0.4)
        #j['isiso'] = ~match(j,fj_clean,1.5)   # What is this ?????
        j['isdcsvL'] = (j.btagDeepB>deepcsvWPs['loose'])
        j['isdflvL'] = (j.btagDeepFlavB>deepflavWPs['loose'])
        j['T'] = TVector2Array.from_polar(j.pt, j.phi)
        j['p4'] = TLorentzVectorArray.from_ptetaphim(j.pt, j.eta, j.phi, j.mass)
        j['ptRaw'] =j.pt * (1-j.rawFactor)
        j['massRaw'] = j.mass * (1-j.rawFactor)
        j['rho'] = j.pt.ones_like()*events.fixedGridRhoFastjetAll.array
        j_good = j[j.isgood.astype(np.bool)]
        j_clean = j_good[j_good.isclean.astype(np.bool)]  # USe this instead of j_iso Sunil
        #j_iso = j_clean[j_clean.isiso.astype(np.bool)]
        j_iso = j_clean[j_clean.astype(np.bool)]    #Sunil changed  
        j_dcsvL = j_iso[j_iso.isdcsvL.astype(np.bool)]
        j_dflvL = j_iso[j_iso.isdflvL.astype(np.bool)]
        j_HEM = j[j.isHEM.astype(np.bool)]
        j_ntot=j.counts
        j_ngood=j_good.counts
        j_nclean=j_clean.counts
        j_niso=j_iso.counts
        j_ndcsvL=j_dcsvL.counts
        j_ndflvL=j_dflvL.counts
        j_nHEM = j_HEM.counts
        leading_j = j[j.pt.argmax()]
        leading_j = leading_j[leading_j.isgood.astype(np.bool)]
        leading_j = leading_j[leading_j.isclean.astype(np.bool)]

        ###
        #Calculating derivatives
        ###

        ele_pairs = e_loose.distincts()
        diele = ele_pairs.i0+ele_pairs.i1
        diele['T'] = TVector2Array.from_polar(diele.pt, diele.phi)
        leading_ele_pair = ele_pairs[diele.pt.argmax()]
        leading_diele = diele[diele.pt.argmax()]

        mu_pairs = mu_loose.distincts()
        dimu = mu_pairs.i0+mu_pairs.i1
        dimu['T'] = TVector2Array.from_polar(dimu.pt, dimu.phi)
        leading_mu_pair = mu_pairs[dimu.pt.argmax()]
        leading_dimu = dimu[dimu.pt.argmax()]

        ###
        # Calculate recoil
        ###   HT,  LT, dPhi,  mT_{W}, MT_misET

        um = met.T+leading_mu.T.sum()
        ue = met.T+leading_e.T.sum()
        umm = met.T+leading_dimu.T.sum()
        uee = met.T+leading_diele.T.sum()
        ua = met.T+leading_pho.T.sum()
        #Need  help from Matteo
        u = {}
        u['sr']=met.T
        u['wecr']=ue
        u['tecr']=ue
        u['wmcr']=um
        u['tmcr']=um
        u['zecr']=uee
        u['zmcr']=umm
        u['gcr']=ua

        ###
        #Calculating weights
        ###
        if not isData:
            
            ###
            # JEC/JER
            ###

            #j['ptGenJet'] = j.matched_gen.pt
            #Jet_transformer.transform(j)

            gen = events.GenPart
            
            #Need to understand this part Sunil
            gen['isb'] = (abs(gen.pdgId)==5)&gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            gen['isc'] = (abs(gen.pdgId)==4)&gen.hasFlags(['fromHardProcess', 'isLastCopy'])

            gen['isTop'] = (abs(gen.pdgId)==6)&gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            gen['isW'] = (abs(gen.pdgId)==24)&gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            gen['isZ'] = (abs(gen.pdgId)==23)&gen.hasFlags(['fromHardProcess', 'isLastCopy'])
            gen['isA'] = (abs(gen.pdgId)==22)&gen.hasFlags(['fromHardProcess', 'isLastCopy'])

            genTops = gen[gen.isTop]
            genWs = gen[gen.isW]
            genZs = gen[gen.isZ]
            genAs = gen[gen.isA]

            nlo  = np.ones(events.size)
            nnlo = np.ones(events.size)
            nnlo_nlo = np.ones(events.size)
            adhoc = np.ones(events.size)
            if('TTJets' in dataset): 
                nlo = np.sqrt(get_ttbar_weight(genTops[:,0].pt.sum()) * get_ttbar_weight(genTops[:,1].pt.sum()))
            #elif('GJets' in dataset): 
            #    nlo = get_nlo_weight['a'](genAs.pt.max())
            elif('WJets' in dataset): 
                #nlo = get_nlo_weight['w'](genWs.pt.max())
                #if self._year != '2016': adhoc = get_adhoc_weight['w'](genWs.pt.max())
                #nnlo = get_nnlo_weight['w'](genWs.pt.max())
                nnlo_nlo = get_nnlo_nlo_weight['w'](genWs.pt.max())*(genWs.pt.max()>100).astype(np.int) + (genWs.pt.max()<=100).astype(np.int)
            elif('DY' in dataset): 
                #nlo = get_nlo_weight['z'](genZs.pt.max())
                #if self._year != '2016': adhoc = get_adhoc_weight['z'](genZs.pt.max())
                #nnlo = get_nnlo_weight['dy'](genZs.pt.max())
                nnlo_nlo = get_nnlo_nlo_weight['dy'](genZs.pt.max())*(genZs.pt.max()>100).astype(np.int) + (genZs.pt.max()<=100).astype(np.int)
            elif('ZJets' in dataset): 
                #nlo = get_nlo_weight['z'](genZs.pt.max())
                #if self._year != '2016': adhoc = get_adhoc_weight['z'](genZs.pt.max())
                #nnlo = get_nnlo_weight['z'](genZs.pt.max())
                nnlo_nlo = get_nnlo_nlo_weight['z'](genZs.pt.max())*(genZs.pt.max()>100).astype(np.int) + (genZs.pt.max()<=100).astype(np.int)

            ###
            # Calculate PU weight and systematic variations
            ###

            pu = get_pu_weight['cen'](events.PV.npvs)
            #puUp = get_pu_weight['up'](events.PV.npvs)
            #puDown = get_pu_weight['down'](events.PV.npvs)

            ###
            # Trigger efficiency weight
            ###
            
            ele1_trig_weight = get_ele_trig_weight(leading_ele_pair.i0.eta.sum(),leading_ele_pair.i0.pt.sum())
            ele2_trig_weight = get_ele_trig_weight(leading_ele_pair.i1.eta.sum(),leading_ele_pair.i1.pt.sum())

            # Need Help from Matteo
            trig = {}

            trig['sre'] = get_ele_trig_weight(leading_e.eta.sum(), leading_e.pt.sum()) 
            trig['srm'] = #Need  be fixed  in Util first 
            trig['ttbare'] = get_ele_trig_weight(leading_e.eta.sum(), leading_e.pt.sum())
            trig['ttbarm'] = #Need  be fixed  in Util first 
            trig['wjete'] = get_ele_trig_weight(leading_e.eta.sum(), leading_e.pt.sum())
            trig['wjetm'] = #Need  be fixed  in Util first 
            trig['dilepe'] = 1 - (1-ele1_trig_weight)*(1-ele2_trig_weight)  
            #trig['dilepm'] =  Need  be fixed  in Util first 

            # For muon ID weights, SFs are given as a function of abs(eta), but in 2016
            ##

            mueta = abs(leading_mu.eta.sum())
            mu1eta=abs(leading_mu_pair.i0.eta.sum())
            mu2eta=abs(leading_mu_pair.i1.eta.sum())
            if self._year=='2016':
                mueta=leading_mu.eta.sum()
                mu1eta=leading_mu_pair.i0.eta.sum()
                mu2eta=leading_mu_pair.i1.eta.sum()

            ### 
            # Calculating electron and muon ID SF and efficiencies (when provided)
            ###

            mu1Tsf = get_mu_tight_id_sf(mu1eta,leading_mu_pair.i0.pt.sum())
            mu2Tsf = get_mu_tight_id_sf(mu2eta,leading_mu_pair.i1.pt.sum())
            mu1Lsf = get_mu_loose_id_sf(mu1eta,leading_mu_pair.i0.pt.sum())
            mu2Lsf = get_mu_loose_id_sf(mu2eta,leading_mu_pair.i1.pt.sum())
    
            e1Tsf  = get_ele_tight_id_sf(leading_ele_pair.i0.eta.sum(),leading_ele_pair.i0.pt.sum())
            e2Tsf  = get_ele_tight_id_sf(leading_ele_pair.i1.eta.sum(),leading_ele_pair.i1.pt.sum())
            e1Lsf  = get_ele_loose_id_sf(leading_ele_pair.i0.eta.sum(),leading_ele_pair.i0.pt.sum())
            e2Lsf  = get_ele_loose_id_sf(leading_ele_pair.i1.eta.sum(),leading_ele_pair.i1.pt.sum())

            e1Teff= get_ele_tight_id_eff(leading_ele_pair.i0.eta.sum(),leading_ele_pair.i0.pt.sum())
            e2Teff= get_ele_tight_id_eff(leading_ele_pair.i1.eta.sum(),leading_ele_pair.i1.pt.sum())
            e1Leff= get_ele_loose_id_eff(leading_ele_pair.i0.eta.sum(),leading_ele_pair.i0.pt.sum())
            e2Leff= get_ele_loose_id_eff(leading_ele_pair.i1.eta.sum(),leading_ele_pair.i1.pt.sum())

            # Need Help from  Matteo
            ids={}
            ids['sre'] = get_ele_tight_id_sf(leading_e.eta.sum(),leading_e.pt.sum())
            ids['srm'] = get_mu_tight_id_sf(mueta,leading_mu.pt.sum())
            ids['ttbare'] = get_ele_tight_id_sf(leading_e.eta.sum(),leading_e.pt.sum())
            ids['ttbarm'] = get_mu_tight_id_sf(mueta,leading_mu.pt.sum())
            ids['wjete'] = get_ele_tight_id_sf(leading_e.eta.sum(),leading_e.pt.sum())
            ids['wjetm'] = get_mu_tight_id_sf(mueta,leading_mu.pt.sum())
            ids['dilepe'] = e1Lsf*e2Lsf
            ids['dilepm'] = mu1Lsf*mu2Lsf


            ###
            # Reconstruction weights for electrons
            ###
            
            e1sf_reco = get_ele_reco_sf(leading_ele_pair.i0.eta.sum(),leading_ele_pair.i0.pt.sum())
            e2sf_reco = get_ele_reco_sf(leading_ele_pair.i1.eta.sum(),leading_ele_pair.i1.pt.sum())
            
            # Need Help from  Matteo 

            reco = {}
            reco['sre'] = get_ele_reco_sf(leading_e.eta.sum(),leading_e.pt.sum())
            reco['srm'] = np.ones(events.size)
            reco['ttbare'] = get_ele_reco_sf(leading_e.eta.sum(),leading_e.pt.sum())
            reco['ttbarm'] = np.ones(events.size)
            reco['wjete'] = get_ele_reco_sf(leading_e.eta.sum(),leading_e.pt.sum())
            reco['wjetm'] = np.ones(events.size)
            reco['dilepe'] = e1sf_reco * e2sf_reco
            reco['dilepm'] = np.ones(events.size)

            ###
            # Isolation weights for muons
            ###

            mu1Tsf_iso = get_mu_tight_iso_sf(mu1eta,leading_mu_pair.i0.pt.sum())
            mu2Tsf_iso = get_mu_tight_iso_sf(mu2eta,leading_mu_pair.i1.pt.sum())
            mu1Lsf_iso = get_mu_loose_iso_sf(mu1eta,leading_mu_pair.i0.pt.sum())
            mu2Lsf_iso = get_mu_loose_iso_sf(mu2eta,leading_mu_pair.i1.pt.sum())

            # Need Help from  Matteo 

            isolation = {}
            isolation['sre'] = np.ones(events.size)
            isolation['srm'] = get_mu_tight_iso_sf(mueta,leading_mu.pt.sum())
            isolation['ttbare'] = np.ones(events.size)
            isolation['ttbarm'] = get_mu_tight_iso_sf(mueta,leading_mu.pt.sum())
            isolation['wjete'] = np.ones(events.size)
            isolation['wjetm'] = get_mu_tight_iso_sf(mueta,leading_mu.pt.sum())
            isolation['dilepe'] = np.ones(events.size)
            isolation['dilepm'] = mu1Lsf_iso*mu2Lsf_iso


            ###
            # AK4 b-tagging weights
            ###

            btag = {}
            btagUp = {}
            btagDown = {}
            # Need Help from  Matteo  
            btag['sr'],   btagUp['sr'],   btagDown['sr']   = get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'0')
            btag['wmcr'], btagUp['wmcr'], btagDown['wmcr'] = get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'0')
            btag['tmcr'], btagUp['tmcr'], btagDown['tmcr'] = get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'-1')
            btag['wecr'], btagUp['wecr'], btagDown['wecr'] = get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'0')
            btag['tecr'], btagUp['tecr'], btagDown['tecr'] = get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'-1')
            btag['zmcr'], btagUp['zmcr'], btagDown['zmcr'] = np.ones(events.size), np.ones(events.size), np.ones(events.size)#get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'0')
            btag['zecr'], btagUp['zecr'], btagDown['zecr'] = np.ones(events.size), np.ones(events.size), np.ones(events.size)#get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'0')
            btag['gcr'],  btagUp['gcr'],  btagDown['gcr']  = np.ones(events.size), np.ones(events.size), np.ones(events.size)#get_deepflav_weight['loose'](j_iso.pt,j_iso.eta,j_iso.hadronFlavour,'0')
            
            for r in selected_regions:
                weights[r] = processor.Weights(len(events))
                weights[r].add('genw',events.genWeight)
                weights[r].add('nlo',nlo)
                #weights[r].add('adhoc',adhoc)
                #weights[r].add('nnlo',nnlo)
                weights[r].add('nnlo_nlo',nnlo_nlo)
                weights[r].add('pileup',pu)#,puUp,puDown)
                weights[r].add('trig', trig[r])
                weights[r].add('ids', ids[r])
                weights[r].add('reco', reco[r])
                weights[r].add('isolation', isolation[r])
                weights[r].add('btag',btag[r], btagUp[r], btagDown[r])
                
        #leading_fj = fj[fj.pt.argmax()]
        #leading_fj = leading_fj[leading_fj.isgood.astype(np.bool)]
        #leading_fj = leading_fj[leading_fj.isclean.astype(np.bool)]
        
        ###
        #Importing the MET filters per year from metfilters.py and constructing the filter boolean
        ###

        met_filters =  np.ones(events.size, dtype=np.bool)
        for flag in AnalysisProcessor.met_filter_flags[self._year]:
            met_filters = met_filters & events.Flag[flag]
        selection.add('met_filters',met_filters)

        triggers = np.zeros(events.size, dtype=np.bool)
        for path in self._met_triggers[self._year]:
            if path not in events.HLT.columns: continue
            triggers = triggers | events.HLT[path]
        selection.add('met_triggers', triggers)

        triggers = np.zeros(events.size, dtype=np.bool)
        for path in self._singleelectron_triggers[self._year]:
            if path not in events.HLT.columns: continue
            triggers = triggers | events.HLT[path]
        selection.add('singleelectron_triggers', triggers)

        triggers = np.zeros(events.size, dtype=np.bool)
        for path in self._singlemuon_triggers[self._year]:
            if path not in events.HLT.columns: continue
            triggers = triggers | events.HLT[path]
        selection.add('singlemuon_triggers', triggers)

        triggers = np.zeros(events.size, dtype=np.bool)
        for path in self._singlephoton_triggers[self._year]:
            if path not in events.HLT.columns: continue
            triggers = triggers | events.HLT[path]
        selection.add('singlephoton_triggers', triggers)

        noHEMj = np.ones(events.size, dtype=np.bool)
        if self._year=='2018': noHEMj = (j_nHEM==0)

        selection.add('iszeroL',
                      (e_nloose==0)&(mu_nloose==0)&(tau_nloose==0)&(pho_nloose==0)
                  )
        selection.add('isoneM', 
                      (e_nloose==0)&(mu_ntight==1)&(tau_nloose==0)&(pho_nloose==0)
                  )
        selection.add('isoneE', 
                      (e_ntight==1)&(mu_nloose==0)&(tau_nloose==0)&(pho_nloose==0)
                  )
        selection.add('istwoM', 
                      #(e_nloose==0)&(mu_ntight>=1)&(mu_nloose==2)&(tau_nloose==0)&(pho_nloose==0)
                      (e_nloose==0)&(mu_nloose==2)&(tau_nloose==0)&(pho_nloose==0)
                      &(leading_dimu.mass.sum()>60)&(leading_dimu.mass.sum()<120)
                      &(leading_dimu.pt.sum()>200)
                  )
        selection.add('istwoE', 
                      #(e_ntight>=1)&(e_nloose==2)&(mu_nloose==0)&(tau_nloose==0)&(pho_nloose==0)
                      (e_nloose==2)&(mu_nloose==0)&(tau_nloose==0)&(pho_nloose==0)
                      &(leading_diele.mass.sum()>60)&(leading_diele.mass.sum()<120)
                      &(leading_diele.pt.sum()>200)
                  )
        selection.add('isoneA', 
                      (e_nloose==0)&(mu_nloose==0)&(tau_nloose==0)&(pho_ntight==1)
                  )
        # Add Btag Selection Sunil HElp Needed  from  Dough/Matteo
        '''
        selection.add('onebjet',
                      (e_nloose==0)&(mu_nloose==0)&(tau_nloose==0)&(pho_ntight==1)
                  )

        '''

        selection.add('noHEMj', noHEMj)
        # Need Help from Matteo
        regions = {}  
        regions['sre'] = {'isoneE','onebjet','noHEMj','met_filters','singlelectron_triggers'}
        regions['srm'] = {'isoneM','onebjet','noHEMj','met_filters','singlmuon_triggers'}
        regions['ttbare'] = {'isoneE','onebjet','noHEMj','met_filters','singlelectron_triggers'}
        regions['ttbarm'] = {'isoneM','onebjet','noHEMj','met_filters','singlmuon_triggers'}
        regions['wjete'] = {'isoneE','onebjet','noHEMj','met_filters','singlelectecon_triggers'}
        regions['wjetm'] = {'isoneM','onebjet','noHEMj','met_filters','singlmuon_triggers'}
        regions['dilepe'] = {'istwoE','onebjet','noHEMj','met_filters','singlelectecon_triggers'}
        regions['dilepm'] = {'istwoM','onebjet','noHEMj','met_filters','singlmuon_triggers'}

        temp={}
        for r in selected_regions: 
            temp[r]=regions[r]
        regions=temp
        temp={}
        
        def fill(dataset, region, systematic, gentype, weight, cut):
            sname = 'nominal' if systematic is None else systematic
            variables = {}
            variables['met']       = met.pt
            variables['j1pt']      = leading_j.pt
            variables['j1eta']     = leading_j.eta
            variables['j1phi']     = leading_j.phi
            variables['e1pt']      = leading_e.pt
            variables['e1phi']     = leading_e.phi
            variables['e1eta']     = leading_e.eta
            variables['dielemass'] = leading_diele.mass
            variables['dielept']   = leading_diele.pt
            variables['mu1pt']     = leading_mu.pt
            variables['mu1phi']    = leading_mu.phi
            variables['mu1eta']    = leading_mu.eta
            variables['dimumass']  = leading_dimu.mass
            variables['dimupt']    = leading_dimu.pt
            variables['njets']     = j_nclean
            variables['ndcsvL']    = j_ndcsvL
            variables['ndflvL']    = j_ndflvL
            
            flat_variables = {k: v[cut].flatten() for k, v in variables.items()}
            flat_weights = {k: (~np.isnan(v[cut])*weight[cut]).flatten() for k, v in variables.items()}
            for histname, h in hout.items():
                if not isinstance(h, hist.Hist):
                    continue
                elif histname == 'sumw':
                    continue
                elif histname == 'recoil':
                    h.fill(dataset=dataset, region=region, systematic=sname, gentype=gentype, recoil=u[region.split('_')[0]].mag, weight=weight*cut)
                elif histname == 'CaloMinusPfOverRecoil':
                    h.fill(dataset=dataset, region=region, systematic=sname, gentype=gentype, CaloMinusPfOverRecoil= abs(calomet.pt - met.pt) / u[region.split('_')[0]].mag, weight=weight*cut)
                elif histname == 'mindphi':
                    h.fill(dataset=dataset, region=region, systematic=sname, gentype=gentype, mindphi=abs(u[region.split('_')[0]].delta_phi(j_clean.T)).min(), weight=weight*cut)
                else:
                    flat_variable = {histname: flat_variables[histname]}
                    h.fill(dataset=dataset, region=region, systematic=sname, gentype=gentype, **flat_variable, weight=flat_weights[histname])

        def get_weight(region,systematic=None):
            region=region.split('_')[0]
            if systematic is not None: return weights[region].weight(modifier=systematic)
            return weights[region].weight()

        systematics = [
            None,
            'btagUp',
            'btagDown',
        ]

        if isData:
            hout['sumw'].fill(dataset=dataset, sumw=1, weight=1)
            for r in regions:
                cut = selection.all(*regions[r])
                fill(dataset, r, None, 'data', np.ones(events.size), cut)
        else:
            # Add back two flavor LF HF for  WJets,  and DY
            if 'WJets' in dataset or 'DY' in dataset:
                whf = ((gen[gen.isb].counts>0)|(gen[gen.isc].counts>0)).astype(np.int)
                wlf = (~(whf.astype(np.bool))).astype(np.int)
                hout['sumw'].fill(dataset='HF--'+dataset, sumw=1, weight=events.genWeight.sum())
                hout['sumw'].fill(dataset='LF--'+dataset, sumw=1, weight=events.genWeight.sum())
                for r in regions:
                    cut = selection.all(*regions[r])
                    for systematic in systematics:
                        fill('HF--'+dataset, r, systematic, gentype, get_weight(r,systematic=systematic)*whf*wgentype[gentype], cut)
                        fill('LF--'+dataset, r, systematic, gentype, get_weight(r,systematic=systematic)*wlf*wgentype[gentype], cut)
            else:
                hout['sumw'].fill(dataset=dataset, sumw=1, weight=events.genWeight.sum())
                for r in regions:
                    cut = selection.all(*regions[r])
                    for systematic in systematics:
                        fill(dataset, r, systematic, gentype, get_weight(r,systematic=systematic), cut)

        return hout

    def postprocess(self, accumulator):
        scale = {}
        for d in accumulator['sumw'].identifiers('dataset'):
            print('Scaling:',d.name)
            dataset = d.name
            if '--' in dataset: dataset = dataset.split('--')[1]
            if self._xsec[dataset]!= -1: scale[d.name] = self._lumi*self._xsec[dataset]
            else: scale[d.name] = 1

        for histname, h in accumulator.items():
            if histname == 'sumw': continue
            if isinstance(h, hist.Hist):
                h.scale(scale, axis='dataset')

        return accumulator

if __name__ == '__main__':
    parser = OptionParser()
    parser.add_option('-y', '--year', help='year', dest='year')
    (options, args) = parser.parse_args()


    with open('metadata/'+options.year+'.json') as fin:
        samplefiles = json.load(fin)
        xsec = {k: v['xs'] for k,v in samplefiles.items()}

    corrections = load('data/corrections.coffea')
    ids         = load('data/ids.coffea')
    common      = load('data/common.coffea')

    processor_instance=AnalysisProcessor(year=options.year,
                                         xsec=xsec,
                                         corrections=corrections,
                                         ids=ids,
                                         common=common)
    
    save(processor_instance, 'data/darkhiggs'+options.year+'.processor')
