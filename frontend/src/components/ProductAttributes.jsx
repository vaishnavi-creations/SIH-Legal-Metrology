import React from 'react';
import {
  Package,
  Tag,
  IndianRupee,
  Scale,
  Calendar,
  Building2,
  PhoneCall,
  Globe,
  Calculator,
  CheckCircle2,
  Layers,
  AlertTriangle
} from 'lucide-react';
import { formatCurrency } from '../utils/formatters';

const ROLE_DISPLAY_NAMES = {
  front: 'Front View',
  back: 'Back View',
  left: 'Left Side',
  right: 'Right Side',
  top: 'Top View',
  bottom: 'Bottom View',
  label: 'Label Panel',
  other: 'Package Face',
};

function formatRole(role) {
  if (!role) return null;
  return ROLE_DISPLAY_NAMES[role.toLowerCase()] || `${role.charAt(0).toUpperCase() + role.slice(1)} View`;
}

export function ProductAttributes({ data, provenance = {}, conflicts = [] }) {
  if (!data) return null;

  const mrpVal = data.mrp?.value !== undefined && data.mrp?.value !== null
    ? formatCurrency(data.mrp.value, data.mrp.currency || 'INR')
    : null;

  const netQty = data.net_quantity?.value !== undefined && data.net_quantity?.value !== null
    ? `${data.net_quantity.value} ${data.net_quantity.unit || ''}`.trim()
    : null;

  const usp = data.unit_sale_price?.value !== undefined && data.unit_sale_price?.value !== null
    ? `${formatCurrency(data.unit_sale_price.value)} per ${data.unit_sale_price.unit || ''}`
    : (data.mrp?.unit_sale_price || null);

  const mfgDate = data.dates?.manufacturing_date || null;
  const packDate = data.dates?.packaging_date || null;
  const expDate = data.dates?.expiry_date || null;
  const bestBefore = data.dates?.best_before || null;

  const mfgAddressParts = [
    data.manufacturer?.name,
    data.manufacturer?.address,
    data.manufacturer?.pincode ? `PIN: ${data.manufacturer.pincode}` : null,
  ].filter(Boolean);

  const consumerCareParts = [
    data.consumer_care?.phone ? `Tel: ${data.consumer_care.phone}` : null,
    data.consumer_care?.email ? `Email: ${data.consumer_care.email}` : null,
    data.consumer_care?.address ? `Addr: ${data.consumer_care.address}` : null,
  ].filter(Boolean);

  const attributes = [
    {
      key: 'product_name',
      icon: Package,
      label: 'Product Name',
      value: data.product_name || data.common_or_generic_name,
      raw: data.common_or_generic_name && data.product_name !== data.common_or_generic_name ? data.common_or_generic_name : null,
    },
    {
      key: 'common_or_generic_name',
      icon: Tag,
      label: 'Brand / Generic Name',
      value: [data.brand, data.common_or_generic_name].filter(Boolean).join(' • ') || null,
      raw: null,
    },
    {
      key: 'mrp',
      icon: IndianRupee,
      label: 'Maximum Retail Price (MRP)',
      value: mrpVal,
      raw: data.mrp?.raw_text,
      badge: data.mrp?.includes_taxes ? 'Inclusive of all taxes' : null,
    },
    {
      key: 'unit_sale_price',
      icon: Calculator,
      label: 'Unit Sale Price (USP)',
      value: usp,
      raw: data.unit_sale_price?.raw_text || (data.mrp?.unit_sale_price ? `Derived from MRP: ${data.mrp.unit_sale_price}` : null),
    },
    {
      key: 'net_quantity',
      icon: Scale,
      label: 'Net Quantity',
      value: netQty,
      raw: data.net_quantity?.raw_text,
    },
    {
      key: 'dates',
      icon: Calendar,
      label: 'Manufacture / Packing Date',
      value: [mfgDate ? `Mfg: ${mfgDate}` : null, packDate ? `Pkd: ${packDate}` : null].filter(Boolean).join(' • ') || null,
      raw: data.dates?.raw_text,
    },
    {
      key: 'dates',
      icon: Calendar,
      label: 'Expiry / Best Before',
      value: [expDate ? `Exp: ${expDate}` : null, bestBefore ? `Best Before: ${bestBefore}` : null].filter(Boolean).join(' • ') || null,
      raw: data.dates?.raw_text && !mfgDate && !packDate ? data.dates.raw_text : null,
    },
    {
      key: 'manufacturer',
      icon: Building2,
      label: data.manufacturer?.entity_type ? `${data.manufacturer.entity_type.toUpperCase()} Name & Address` : 'Manufacturer / Packer Name & Address',
      value: mfgAddressParts.length > 0 ? mfgAddressParts.join(', ') : null,
      raw: data.manufacturer?.raw_text,
    },
    {
      key: 'country_of_origin',
      icon: Globe,
      label: 'Country of Origin',
      value: data.country_of_origin,
      raw: null,
    },
    {
      key: 'consumer_care',
      icon: PhoneCall,
      label: 'Consumer Care Details',
      value: consumerCareParts.length > 0 ? consumerCareParts.join(' • ') : null,
      raw: data.consumer_care?.raw_text,
    },
  ];

  return (
    <div className="bg-white rounded-2xl border border-slate-200 shadow-sm overflow-hidden">
      <div className="px-5 py-3.5 bg-slate-50 border-b border-slate-200 flex items-center justify-between">
        <h4 className="text-xs sm:text-sm font-bold text-navy-900 flex items-center gap-2">
          <Package size={16} className="text-emerald-600" />
          <span>Extracted Product Declarations</span>
        </h4>
        <span className="text-[10px] font-mono font-bold uppercase tracking-wider text-emerald-800 bg-emerald-100/70 px-2 py-0.5 rounded border border-emerald-200">
          Structured & Evidence
        </span>
      </div>

      <div className="divide-y divide-slate-100">
        {attributes.map((attr, idx) => {
          const Icon = attr.icon;
          const isPresent = Boolean(attr.value);

          // Resolve provenance and conflict status for this attribute
          const prov = (provenance && attr.key ? provenance[attr.key] : null) ||
            (attr.key === 'product_name' && provenance?.common_or_generic_name ? provenance.common_or_generic_name : null);

          const sourceRole = prov?.source_role ? formatRole(prov.source_role) : null;
          const isCorroborated = Boolean(prov?.is_corroborated);
          const corroboratingSources = Array.isArray(prov?.corroborating_sources) ? prov.corroborating_sources : [];
          const corroborationCount = corroboratingSources.length;
          const hasConflict = Boolean(prov?.has_conflict || (conflicts && conflicts.some(c => c.field_name === attr.key)));

          return (
            <div key={idx} className="p-3.5 sm:px-5 hover:bg-slate-50/50 transition-colors">
              <div className="flex items-start justify-between gap-3">
                <div className="flex items-center gap-2 text-slate-700 shrink-0">
                  <Icon size={14} className={isPresent ? "text-emerald-600" : "text-slate-300"} />
                  <span className="text-xs font-bold">{attr.label}</span>
                </div>

                <div className="text-right flex-1">
                  {isPresent ? (
                    <div>
                      <span className="text-xs sm:text-sm font-bold text-navy-950 break-words">
                        {attr.value}
                      </span>
                      {attr.badge && (
                        <span className="ml-2 text-[10px] font-semibold text-emerald-700 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded">
                          {attr.badge}
                        </span>
                      )}
                    </div>
                  ) : (
                    <span className="text-xs text-slate-400 italic">
                      Not declared on label
                    </span>
                  )}

                  {/* Compact Evidence Fusion Badges: Source Role, Corroboration, Conflict Alert */}
                  {(sourceRole || isCorroborated || hasConflict) && (
                    <div className="mt-1 flex flex-wrap items-center justify-end gap-1.5">
                      {sourceRole && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-mono font-bold text-slate-700 bg-slate-100 border border-slate-200 px-1.5 py-0.5 rounded shadow-2xs">
                          <Layers size={10} className="text-slate-500" />
                          <span>{sourceRole}</span>
                        </span>
                      )}

                      {isCorroborated && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-emerald-800 bg-emerald-50 border border-emerald-200 px-1.5 py-0.5 rounded shadow-2xs">
                          <CheckCircle2 size={10} className="text-emerald-600 shrink-0" />
                          <span>
                            {corroborationCount > 1
                              ? `Corroborated on ${corroborationCount} faces`
                              : 'Corroborated across views'}
                          </span>
                        </span>
                      )}

                      {hasConflict && (
                        <span className="inline-flex items-center gap-1 text-[10px] font-bold text-amber-900 bg-amber-100 border border-amber-300 px-1.5 py-0.5 rounded shadow-2xs">
                          <AlertTriangle size={10} className="text-amber-700 shrink-0" />
                          <span>Conflicting values detected</span>
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>

              {/* Raw detected text audit */}
              {attr.raw && (
                <div className="mt-1.5 pt-1 border-t border-slate-100/70 flex items-baseline justify-end gap-1.5 text-[11px] font-mono text-slate-500">
                  <span className="text-[10px] uppercase font-bold text-slate-400">Raw:</span>
                  <span className="truncate max-w-sm sm:max-w-md bg-slate-50 px-1.5 py-0.5 rounded border border-slate-200/60 text-slate-700">
                    {attr.raw}
                  </span>
                </div>
              )}
            </div>
          );
        })}
      </div>

    </div>
  );
}
