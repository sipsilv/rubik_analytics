import React, { useState, useEffect } from 'react';
import { Tabs, Tab } from '@/components/ui/Tabs';
import { FinancialsPanelHeader } from '@/components/FinancialsPanelHeader';
import { FinancialsPNLTab } from '@/components/FinancialsPNLTab';
import { FinancialsBalanceSheetTab } from '@/components/FinancialsBalanceSheetTab';
import { FinancialsCashFlowTab } from '@/components/FinancialsCashFlowTab';
import { CorporateActionsPanel } from '@/components/CorporateActionsPanel';

export default function FinancialsAndCorporateActionsPanel({ symbol }: { symbol: string }) {
  const [activeTab, setActiveTab] = useState<'pnl' | 'balance' | 'cashflow'>('pnl');
  const [period, setPeriod] = useState<'quarterly' | 'annual'>('quarterly');
  const [nature, setNature] = useState<'standalone' | 'consolidated'>('standalone');

  // Optionally, fetch header info here

  return (
    <div className="w-full max-w-5xl mx-auto p-4">
      <FinancialsPanelHeader symbol={symbol} />
      <div className="mt-4">
        <Tabs value={activeTab} onValueChange={setActiveTab}>
          <Tab value="pnl" label="Profit & Loss">
            <FinancialsPNLTab symbol={symbol} period={period} nature={nature} />
          </Tab>
          <Tab value="balance" label="Balance Sheet">
            <FinancialsBalanceSheetTab symbol={symbol} period={period} nature={nature} />
          </Tab>
          <Tab value="cashflow" label="Cash Flow">
            <FinancialsCashFlowTab symbol={symbol} period={period} nature={nature} />
          </Tab>
        </Tabs>
        <div className="flex gap-4 mt-2">
          <button
            className={`btn ${period === 'quarterly' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setPeriod('quarterly')}
          >
            Quarterly
          </button>
          <button
            className={`btn ${period === 'annual' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setPeriod('annual')}
          >
            Annual
          </button>
          <button
            className={`btn ${nature === 'standalone' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setNature('standalone')}
          >
            Standalone
          </button>
          <button
            className={`btn ${nature === 'consolidated' ? 'btn-primary' : 'btn-outline'}`}
            onClick={() => setNature('consolidated')}
          >
            Consolidated
          </button>
        </div>
      </div>
      <div className="mt-8">
        <CorporateActionsPanel symbol={symbol} />
      </div>
    </div>
  );
}
