"""
Module de génération de rapports EIOPA
"""
from pathlib import Path
from typing import Dict, Optional
from datetime import datetime

from config.config import LATEST_REPORT_FILE
from src.utils import setup_logging, format_bps, format_rate_pct

logger = setup_logging()


class EIOPAReporter:
    """Générateur de rapports d'analyse EIOPA"""
    
    @staticmethod
    def generate_text_report(analysis: Dict, output_file: Optional[Path] = None) -> str:
        """
        Génère un rapport texte formaté
        
        Args:
            analysis: Résultat de l'analyse (analyzer.analyze())
            output_file: Fichier de sortie (optionnel)
            
        Returns:
            Texte du rapport
        """
        lines = []
        
        # En-tête
        lines.append("=" * 80)
        lines.append("RAPPORT MENSUEL EIOPA - TAUX SANS RISQUE ET VOLATILITY ADJUSTMENT")
        lines.append("=" * 80)
        lines.append("")
        
        # Informations générales
        ref_date = analysis['reference_date']
        lines.append(f"📅 Date d'analyse : {ref_date.strftime('%d/%m/%Y')}")
        lines.append(f"🌍 Pays           : {analysis['country']}")
        lines.append(f"📦 Source         : {analysis.get('source_file', 'N/A')}")
        lines.append("")
        
        # Section : Données extraites
        lines.append("-" * 80)
        lines.append("📊 DONNÉES EXTRAITES")
        lines.append("-" * 80)
        lines.append("")
        
        # Courbe des taux
        lines.append("Courbe des taux sans risque (EUR):")
        for maturity in sorted(analysis['rates'].keys()):
            rate = analysis['rates'][maturity]
            lines.append(f"  • Taux {maturity:2d}Y : {format_rate_pct(rate)}")
        
        lines.append("")
        
        # Volatility Adjustment
        if analysis.get('va') is not None:
            lines.append(f"Volatility Adjustment (VA) : {format_rate_pct(analysis['va'])}")
        else:
            lines.append("Volatility Adjustment (VA) : Non disponible")
        
        lines.append("")
        
        # Section : Métadonnées techniques
        if analysis.get('metadata'):
            lines.append("-" * 80)
            lines.append("🔧 MÉTADONNÉES TECHNIQUES")
            lines.append("-" * 80)
            lines.append("")
            
            metadata = analysis['metadata']
            
            if 'LLP' in metadata:
                lines.append(f"Last Liquid Point (LLP)    : {metadata['LLP']} ans")
            
            if 'Convergence' in metadata:
                lines.append(f"Période de convergence     : {metadata['Convergence']} ans")
            
            if 'UFR' in metadata:
                lines.append(f"Ultimate Forward Rate (UFR): {metadata['UFR']:.2f}%")
            
            if 'alpha' in metadata:
                lines.append(f"Paramètre alpha (Smith-W)  : {metadata['alpha']:.6f}")
            
            if 'CRA' in metadata:
                lines.append(f"Credit Risk Adjustment     : {metadata['CRA']:.0f} bps")
            
            if 'Coupon_freq' in metadata:
                lines.append(f"Fréquence de coupon        : {int(metadata['Coupon_freq'])}")
            
            lines.append("")
        
        # Section : Évolutions M/M
        if analysis['changes_mom'] and analysis.get('previous_date'):
            lines.append("-" * 80)
            lines.append("📈 ÉVOLUTIONS vs MOIS PRÉCÉDENT")
            lines.append("-" * 80)
            lines.append("")
            
            prev_date = analysis['previous_date']
            lines.append(f"Référence : {prev_date.strftime('%d/%m/%Y')}")
            lines.append("")
            
            lines.append("Variation des taux (en points de base):")
            for maturity in sorted([k for k in analysis['changes_mom'].keys() if k != 'va']):
                change = analysis['changes_mom'][maturity]
                indicator = "🔴" if abs(change) >= 50 else "🟢"
                lines.append(f"  {indicator} Taux {maturity:2d}Y : {format_bps(change)}")
            
            if 'va' in analysis['changes_mom']:
                va_change = analysis['changes_mom']['va']
                lines.append(f"  • VA        : {format_bps(va_change)}")
            
            lines.append("")
        
        # Section : Évolutions YTD
        if analysis['changes_ytd'] and analysis.get('ytd_date'):
            lines.append("-" * 80)
            lines.append("📆 ÉVOLUTIONS DEPUIS DÉBUT D'ANNÉE (YTD)")
            lines.append("-" * 80)
            lines.append("")
            
            ytd_date = analysis['ytd_date']
            lines.append(f"Référence : {ytd_date.strftime('%d/%m/%Y')}")
            lines.append("")
            
            lines.append("Variation des taux (en points de base):")
            for maturity in sorted([k for k in analysis['changes_ytd'].keys() if k != 'va']):
                change = analysis['changes_ytd'][maturity]
                indicator = "🔴" if abs(change) >= 100 else "🟢"
                lines.append(f"  {indicator} Taux {maturity:2d}Y : {format_bps(change)}")
            
            if 'va' in analysis['changes_ytd']:
                va_change = analysis['changes_ytd']['va']
                lines.append(f"  • VA        : {format_bps(va_change)}")
            
            lines.append("")
        
        # Section : Alertes
        if analysis.get('alerts'):
            lines.append("-" * 80)
            lines.append("⚠️  ALERTES")
            lines.append("-" * 80)
            lines.append("")
            
            for alert in analysis['alerts']:
                lines.append(f"  {alert}")
            
            lines.append("")
        else:
            lines.append("-" * 80)
            lines.append("✅ Aucune variation anormale détectée")
            lines.append("-" * 80)
            lines.append("")
        
        # Pied de page
        lines.append("=" * 80)
        lines.append(f"Rapport généré le {datetime.now().strftime('%d/%m/%Y à %H:%M:%S')}")
        lines.append("Source : EIOPA Risk-Free Interest Rate Term Structures")
        lines.append("=" * 80)
        
        report_text = "\n".join(lines)
        
        # Sauvegarder dans un fichier si spécifié
        if output_file:
            try:
                output_file.parent.mkdir(parents=True, exist_ok=True)
                with open(output_file, 'w', encoding='utf-8') as f:
                    f.write(report_text)
                logger.info(f"Rapport sauvegardé : {output_file}")
            except Exception as e:
                logger.error(f"Erreur lors de la sauvegarde du rapport : {e}")
        
        return report_text
    
    @staticmethod
    def generate_csv_report(analysis: Dict, output_file: Path):
        """
        Génère un rapport CSV (format tabulaire)
        
        Args:
            analysis: Résultat de l'analyse
            output_file: Fichier de sortie CSV
        """
        import pandas as pd
        
        rows = []
        
        ref_date_str = analysis['reference_date'].strftime('%Y-%m-%d')
        
        # Lignes de taux
        for maturity in sorted(analysis['rates'].keys()):
            row = {
                'reference_date': ref_date_str,
                'country': analysis['country'],
                'type': f'rate_{maturity}y',
                'value': analysis['rates'][maturity],
                'value_pct': analysis['rates'][maturity] * 100
            }
            
            # Ajouter les variations si disponibles
            if maturity in analysis['changes_mom']:
                row['change_mom_bps'] = analysis['changes_mom'][maturity]
            
            if maturity in analysis['changes_ytd']:
                row['change_ytd_bps'] = analysis['changes_ytd'][maturity]
            
            rows.append(row)
        
        # Ligne VA
        if analysis.get('va') is not None:
            row = {
                'reference_date': ref_date_str,
                'country': analysis['country'],
                'type': 'va',
                'value': analysis['va'],
                'value_pct': analysis['va'] * 100
            }
            
            if 'va' in analysis['changes_mom']:
                row['change_mom_bps'] = analysis['changes_mom']['va']
            
            if 'va' in analysis['changes_ytd']:
                row['change_ytd_bps'] = analysis['changes_ytd']['va']
            
            rows.append(row)
        
        df = pd.DataFrame(rows)
        
        try:
            df.to_csv(output_file, index=False)
            logger.info(f"Rapport CSV sauvegardé : {output_file}")
        except Exception as e:
            logger.error(f"Erreur lors de la sauvegarde CSV : {e}")
    
    @staticmethod
    def generate_excel_report(analysis: Dict, output_file: Path):
        """
        Génère un rapport Excel avec plusieurs feuilles
        
        Args:
            analysis: Résultat de l'analyse
            output_file: Fichier de sortie Excel
        """
        import pandas as pd
        
        try:
            with pd.ExcelWriter(output_file, engine='openpyxl') as writer:
                # Feuille 1 : Taux actuels
                rates_data = []
                for maturity in sorted(analysis['rates'].keys()):
                    rates_data.append({
                        'Maturité': f'{maturity}Y',
                        'Taux (%)': analysis['rates'][maturity] * 100
                    })
                
                df_rates = pd.DataFrame(rates_data)
                df_rates.to_excel(writer, sheet_name='Taux actuels', index=False)
                
                # Feuille 2 : Variations M/M
                if analysis['changes_mom']:
                    mom_data = []
                    for maturity in sorted([k for k in analysis['changes_mom'].keys() if k != 'va']):
                        mom_data.append({
                            'Maturité': f'{maturity}Y',
                            'Variation (bps)': analysis['changes_mom'][maturity]
                        })
                    
                    df_mom = pd.DataFrame(mom_data)
                    df_mom.to_excel(writer, sheet_name='Variations M_M', index=False)
                
                # Feuille 3 : Variations YTD
                if analysis['changes_ytd']:
                    ytd_data = []
                    for maturity in sorted([k for k in analysis['changes_ytd'].keys() if k != 'va']):
                        ytd_data.append({
                            'Maturité': f'{maturity}Y',
                            'Variation (bps)': analysis['changes_ytd'][maturity]
                        })
                    
                    df_ytd = pd.DataFrame(ytd_data)
                    df_ytd.to_excel(writer, sheet_name='Variations YTD', index=False)
                
                # Feuille 4 : Synthèse
                summary_data = {
                    'Indicateur': ['Date de référence', 'Pays', 'Nombre de taux'],
                    'Valeur': [
                        analysis['reference_date'].strftime('%Y-%m-%d'),
                        analysis['country'],
                        len(analysis['rates'])
                    ]
                }
                
                if analysis.get('va') is not None:
                    summary_data['Indicateur'].append('VA (%)')
                    summary_data['Valeur'].append(f"{analysis['va'] * 100:.2f}")
                
                df_summary = pd.DataFrame(summary_data)
                df_summary.to_excel(writer, sheet_name='Synthèse', index=False)
            
            logger.info(f"Rapport Excel sauvegardé : {output_file}")
            
        except Exception as e:
            logger.error(f"Erreur lors de la génération Excel : {e}")
    
    @staticmethod
    def print_console_report(analysis: Dict):
        """
        Affiche un rapport dans la console
        
        Args:
            analysis: Résultat de l'analyse
        """
        report = EIOPAReporter.generate_text_report(analysis)
        print(report)


def main():
    """Test du module de reporting"""
    from downloader import EIOPADownloader
    from processor import EIOPAProcessor
    from src.analyzer import EIOPAAnalyzer
    
    # Pipeline complet
    downloader = EIOPADownloader()
    zip_path = downloader.download_latest()
    
    if not zip_path:
        print("✗ Échec du téléchargement")
        return
    
    processor = EIOPAProcessor(zip_path)
    current_data = processor.process()
    
    if not current_data:
        print("✗ Échec du traitement")
        return
    
    # Analyser
    analyzer = EIOPAAnalyzer()
    analyzer.add_to_historical(current_data)
    analysis = analyzer.analyze(current_data)
    
    # Générer les rapports
    reporter = EIOPAReporter()
    
    # Console
    print("\n" + "=" * 80)
    print("RAPPORT CONSOLE")
    print("=" * 80)
    reporter.print_console_report(analysis)
    
    # Texte
    text_file = LATEST_REPORT_FILE
    reporter.generate_text_report(analysis, text_file)
    print(f"\n✓ Rapport texte sauvegardé : {text_file}")
    
    # CSV
    csv_file = LATEST_REPORT_FILE.with_suffix('.csv')
    reporter.generate_csv_report(analysis, csv_file)
    print(f"✓ Rapport CSV sauvegardé : {csv_file}")
    
    # Excel
    excel_file = LATEST_REPORT_FILE.with_suffix('.xlsx')
    reporter.generate_excel_report(analysis, excel_file)
    print(f"✓ Rapport Excel sauvegardé : {excel_file}")


if __name__ == "__main__":
    main()